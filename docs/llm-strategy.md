# LLM Strategy

This document describes the LLM model strategy for ai-incident-commander:
the local + cloud model mix, task-based routing, per-model cost tracking,
cost optimization, escalation strategy, and environment variable
configuration.

All details are derived from `src/incident_commander/config.py`
(`LLMConfig`) and `src/incident_commander/llm_router.py` (`LLMRouter`).

---

## Local + Cloud LLM Mix

ai-incident-commander uses an **OpenAI-compatible API** for all LLM calls,
which means any provider exposing that interface can be used. The default
configuration targets a **local Ollama** instance; cloud providers (OpenAI,
Anthropic) are optional and can be enabled per task.

### Default: Local (Ollama)

```python
# config.py — LLMConfig defaults
analysis_model: str = "ollama/qwen2.5-coder:7b"
analysis_base_url: str = "http://localhost:11434/v1"  # Ollama OpenAI-compatible endpoint
```

Ollama runs models locally on your machine (or a dedicated GPU host). It
exposes an OpenAI-compatible API at `http://localhost:11434/v1`, so the
router's `httpx` POST to `{base_url}/chat/completions` works without any
code changes. Local models are **free** — no per-token billing.

### Optional: Cloud (OpenAI / Anthropic)

Cloud models are configured by setting the task-specific model fields on
`LLMConfig`. The router uses OpenAI-compatible endpoints, so any provider
that exposes that interface works:

| Provider | Example model | Endpoint |
|----------|--------------|----------|
| OpenAI | `gpt-4o`, `gpt-4o-mini` | `https://api.openai.com/v1` |
| Anthropic | `claude-3-5-sonnet` | OpenAI-compatible proxy or native adapter |
| OpenCode Zen | any Zen-hosted model | Zen's OpenAI-compatible endpoint |

> **OpenCode Zen:** Because the router speaks the OpenAI-compatible protocol,
> any OpenCode Zen model endpoint that exposes `/chat/completions` can be
> used by setting the appropriate `*_model` and `*_base_url` fields (and
> `LLM_API_KEY`). Zen-hosted models are configured identically to any other
> OpenAI-compatible provider — no special integration is required.

### Single-model vs. multi-model setups

The configuration supports two deployment patterns:

**Single-model (default):** Only `analysis_model` is set. All tasks fall back
to it. This is the simplest setup — one local model handles everything.

**Multi-model (production):** Set `comms_model` and/or `postmortem_model` to
route different tasks to different models. For example, a powerful local
model for analysis and a cheaper cloud model for routine comms.

---

## Model Routing

The `LLMRouter._resolve_model()` method (`llm_router.py:153`) selects the
model and base URL based on the **task type** passed to `generate()`:

```python
def _resolve_model(self, task: str) -> tuple[str, str | None]:
    llm: LLMConfig = self._config.llm
    if task == "comms" and llm.comms_model:
        return llm.comms_model, llm.comms_base_url
    if task == "postmortem" and llm.postmortem_model:
        return llm.postmortem_model, llm.postmortem_base_url
    return llm.analysis_model, llm.analysis_base_url
```

### Task → model routing table

| Task | Primary model | Fallback (if primary not set) |
|------|--------------|-------------------------------|
| `analysis` | `llm.analysis_model` | — (always used as the base) |
| `comms` | `llm.comms_model` | `llm.analysis_model` |
| `postmortem` | `llm.postmortem_model` | `llm.analysis_model` |

### Which nodes use which task

| Node | LLM task | Default model |
|------|----------|---------------|
| `suggest_remediation_node` | `analysis` | `ollama/qwen2.5-coder:7b` (local, free) |
| `dry_run_simulate_node` | `analysis` | `ollama/qwen2.5-coder:7b` (local, free) |
| `draft_update_node` | `comms` | falls back to `analysis_model` if `comms_model` is `None` |
| `generate_postmortem_node` | `postmortem` | falls back to `analysis_model` if `postmortem_model` is `None` |

### Fallback chain explained

The fallback design lets you start with a single local model and
incrementally add cloud models for specific tasks:

```
   Task: "comms"
      │
      ├── comms_model is set? ── YES ──► use comms_model + comms_base_url
      │
      └── comms_model is None? ── YES ──► fall back to analysis_model + analysis_base_url

   Task: "postmortem"
      │
      ├── postmortem_model is set? ── YES ──► use postmortem_model + postmortem_base_url
      │
      └── postmortem_model is None? ── YES ──► fall back to analysis_model + analysis_base_url

   Task: "analysis"
      │
      └── always uses analysis_model + analysis_base_url
```

This means:
- **Analysis tasks** (remediation suggestions, dry-run simulation) always use
  the configured analysis model — typically the most capable local model.
- **Comms tasks** (stakeholder updates) can use a cheaper/faster model if
  `comms_model` is set, otherwise reuse the analysis model.
- **Postmortem tasks** can use a more articulate model if `postmortem_model`
  is set, otherwise reuse the analysis model.

---

## Cost Tracking Per Model

### Pricing table

Cost is estimated from `LLMConfig.model_pricing` (`config.py:25`), which maps
model IDs to per-1M-token USD rates:

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Cost |
|-------|--------------------|---------------------|------|
| `ollama/qwen2.5-coder:7b` | $0.00 | $0.00 | **Free** (local) |
| `gpt-4o-mini` | $0.15 | $0.60 | Cheap cloud |
| `gpt-4o` | $2.50 | $10.00 | Expensive cloud |
| `claude-3-5-sonnet` | $3.00 | $15.00 | Most expensive |

Unknown models default to `{"input": 0.0, "output": 0.0}` (free), so the cost
report never fails due to missing pricing entries.

### Cost calculation

```python
# llm_router.py:168
cost = (input_tokens / 1_000_000 * pricing["input"]) + \
       (output_tokens / 1_000_000 * pricing["output"])
```

Result is rounded to 6 decimal places.

### Example cost scenarios

**All-local (default):**
- 5 LLM calls × ~500 input tokens × ~200 output tokens
- Total: ~3,500 tokens
- Cost: **$0.00** (Ollama is free)

**Analysis on local + comms on gpt-4o-mini:**
- 2 analysis calls on Ollama: $0.00
- 1 comms call on gpt-4o-mini (500 in / 200 out): $0.000075 + $0.00012 = $0.000195
- Total: **~$0.0002**

**All on gpt-4o:**
- 5 calls × (500 in / 200 out) = 2,500 in / 1,000 out
- Input: 2,500/1M × $2.50 = $0.00625
- Output: 1,000/1M × $10.00 = $0.01
- Total: **~$0.016**

### Cost report output

At graph exit, `cost_report_node` aggregates all `NodeCost` records into a
`CostReport` containing:
- `total_input_tokens`, `total_output_tokens`, `total_tokens`
- `total_estimated_cost_usd`
- `per_node` breakdown (model, tokens, cost, latency per call)
- `models_used` (distinct model IDs invoked)

Every individual LLM call is also logged to
`~/.incident-commander/logs/llm-calls.jsonl` by `LLMObserver` for post-hoc
analysis.

---

## Cost Optimization Tips

### 1. Default to local models

The out-of-the-box configuration uses `ollama/qwen2.5-coder:7b` for all
tasks at **$0.00 cost**. For most incidents, a 7B local model is sufficient
for drafting updates, suggesting remediations, and generating postmortems.

### 2. Use task-specific routing to minimize cloud spend

Only route to cloud models for tasks where local quality is insufficient:

```python
from incident_commander.config import Config, LLMConfig

config = Config(llm=LLMConfig(
    analysis_model="ollama/qwen2.5-coder:7b",     # free — handles analysis
    comms_model="gpt-4o-mini",                     # $0.15/$0.60 — cheap, articulate
    comms_base_url="https://api.openai.com/v1",
    postmortem_model="gpt-4o-mini",                # cheap cloud for long-form writing
    postmortem_base_url="https://api.openai.com/v1",
))
```

This keeps analysis free while using a cheap cloud model for comms and
postmortems where articulateness matters.

### 3. Reserve expensive models for complex incidents

`gpt-4o` ($2.50/$10.00) and `claude-3-5-sonnet` ($3.00/$15.00) are 15-20x
more expensive than `gpt-4o-mini`. Use them only for SEV1 incidents where
root-cause analysis quality is critical. See the escalation strategy below.

### 4. Monitor token usage

Review the per-node cost breakdown in the `CostReport` after each session.
The `llm-calls.jsonl` log provides per-call granularity for identifying
which nodes consume the most tokens.

### 5. Leverage prompt truncation

The router truncates prompts to 8,000 characters (`llm_router.py:231`) and
caps `max_tokens` at 1,024 (`llm_router.py:232`). This prevents runaway
costs from oversized prompts or verbose completions. The remediation and
postmortem nodes further limit context (top-3 to top-5 evidence items) to
keep prompts within budget.

### 6. Use mock LLM for testing

Pass a `mock_llm` callable to `build_graph()` or `LLMRouter` to run the full
graph without any real API calls — zero cost, zero latency, reproducible
results for CI and unit tests.

---

## Escalation Strategy

The recommended strategy is to **start local** and escalate to cloud models
only when an incident's complexity demands it.

### Tier 1: All-local (default)

```
analysis  → ollama/qwen2.5-coder:7b  (free)
comms     → ollama/qwen2.5-coder:7b  (free, fallback)
postmortem → ollama/qwen2.5-coder:7b (free, fallback)
```

- **Use for:** SEV3 incidents, demos, testing, CI
- **Cost:** $0.00
- **Quality:** Good for straightforward incidents with clear runbook matches

### Tier 2: Local analysis + cloud comms

```
analysis  → ollama/qwen2.5-coder:7b  (free)
comms     → gpt-4o-mini              ($0.15/$0.60 per 1M)
postmortem → gpt-4o-mini             ($0.15/$0.60 per 1M)
```

- **Use for:** SEV2 incidents where stakeholder communication quality matters
- **Cost:** ~$0.001-0.01 per incident
- **Quality:** Articulate comms and postmortems; local analysis keeps costs
  near zero

### Tier 3: Cloud for everything

```
analysis  → gpt-4o                   ($2.50/$10.00 per 1M)
comms     → gpt-4o-mini              ($0.15/$0.60 per 1M)
postmortem → gpt-4o-mini             ($0.15/$0.60 per 1M)
```

- **Use for:** SEV1 incidents with complex root-cause analysis where local
  model quality is insufficient
- **Cost:** ~$0.01-0.05 per incident
- **Quality:** Strongest analysis; cheap cloud for routine comms

### Tier 4: Premium cloud

```
analysis  → claude-3-5-sonnet        ($3.00/$15.00 per 1M)
comms     → gpt-4o                   ($2.50/$10.00 per 1M)
postmortem → claude-3-5-sonnet       ($3.00/$15.00 per 1M)
```

- **Use for:** Customer-facing SEV1 incidents requiring the highest-quality
  analysis and communication
- **Cost:** ~$0.05-0.20 per incident
- **Quality:** Best available; use sparingly

### Implementing escalation

Switch tiers by changing the `Config` at runtime:

```python
from incident_commander.config import Config, LLMConfig

# Tier 1 — all local (default)
config = Config()

# Tier 2 — local analysis + cloud comms
config = Config(llm=LLMConfig(
    comms_model="gpt-4o-mini",
    comms_base_url="https://api.openai.com/v1",
    postmortem_model="gpt-4o-mini",
    postmortem_base_url="https://api.openai.com/v1",
))

# Tier 3 — cloud analysis
config = Config(llm=LLMConfig(
    analysis_model="gpt-4o",
    analysis_base_url="https://api.openai.com/v1",
    comms_model="gpt-4o-mini",
    comms_base_url="https://api.openai.com/v1",
))
```

A production deployment could auto-select the tier based on severity:

```python
def config_for_severity(severity: str) -> Config:
    if severity == "SEV1":
        return Config(llm=LLMConfig(
            analysis_model="gpt-4o",
            analysis_base_url="https://api.openai.com/v1",
            comms_model="gpt-4o-mini",
            comms_base_url="https://api.openai.com/v1",
        ))
    if severity == "SEV2":
        return Config(llm=LLMConfig(
            comms_model="gpt-4o-mini",
            comms_base_url="https://api.openai.com/v1",
        ))
    return Config()  # SEV3 — all local
```

---

## Environment Variable Configuration

### `LLM_API_KEY`

The only environment variable read by the router is `LLM_API_KEY`
(`llm_router.py:222`):

```python
api_key = os.environ.get("LLM_API_KEY", "")
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
```

This key is sent as a Bearer token to the LLM endpoint. It is required for
cloud providers (OpenAI, Anthropic, OpenCode Zen) and **not needed** for
local Ollama (which ignores the header).

### Setting it

```bash
# For OpenAI
export LLM_API_KEY="sk-..."

# For Anthropic (via OpenAI-compatible proxy)
export LLM_API_KEY="sk-ant-..."

# For OpenCode Zen
export LLM_API_KEY="zen-..."

# For local Ollama — not required (no key needed)
# LLM_API_KEY can be unset or empty
```

### Endpoint configuration

Model names and base URLs are configured via `LLMConfig` (Python), not
environment variables. To use a cloud endpoint, set the `*_base_url` field
to the provider's OpenAI-compatible URL:

| Provider | Base URL |
|----------|----------|
| Ollama (default) | `http://localhost:11434/v1` |
| OpenAI | `https://api.openai.com/v1` |
| OpenCode Zen | (Zen's OpenAI-compatible endpoint URL) |

### Complete cloud configuration example

```python
from incident_commander.config import Config, LLMConfig

config = Config(llm=LLMConfig(
    analysis_model="gpt-4o",
    analysis_base_url="https://api.openai.com/v1",
    comms_model="gpt-4o-mini",
    comms_base_url="https://api.openai.com/v1",
    postmortem_model="gpt-4o-mini",
    postmortem_base_url="https://api.openai.com/v1",
))
```

With `LLM_API_KEY` set in the environment, the router will authenticate
against the cloud endpoint for all three task types.

### Adding custom model pricing

If you use a model not in the default pricing table, add it to
`model_pricing` so costs are tracked accurately:

```python
config = Config(llm=LLMConfig(
    analysis_model="my-custom-model",
    analysis_base_url="https://my-llm-host/v1",
    model_pricing={
        **LLMConfig().model_pricing,  # keep defaults
        "my-custom-model": {"input": 1.00, "output": 4.00},
    },
))
```

Models not in the pricing table default to free ($0.00), so costs will
show as $0.00 unless you add an entry.
