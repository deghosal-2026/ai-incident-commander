# ai-incident-commander

> CLI tool for incident response: ingest alerts and logs, build timelines, suggest remediation, and auto-generate COE-format postmortems. All powered by local or cloud LLMs. Zero config, zero credentials to start.

[![CI](https://github.com/deghosal-2026/ai-incident-commander/actions/workflows/ci.yml/badge.svg)](https://github.com/deghosal-2026/ai-incident-commander/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/ai-incident-commander.svg)](https://pypi.org/project/ai-incident-commander/)

---

## Quickstart

```bash
pip install ai-incident-commander

# Run a SEV1 payment-service outage — zero config
incident-commander simulate --service payment-service --severity SEV1 --auto-approve

# Output is written to ./output/
```

That's it. No API keys, no cloud accounts, no Docker. The tool uses a local LLM (Ollama/MLX) by default.

---

## What It Does

| Step | What happens |
|------|-------------|
| **Ingest** | Load incident data from CLI flags, input directory, or Python API |
| **Build timeline** | Merge alerts, logs, chat messages, GitHub PRs into a chronological timeline with trust hierarchy |
| **Correlate deploys** | Flag GitHub PRs merged within 30 minutes of the alert as deploy correlations |
| **Retrieve runbooks** | Search runbooks and past incidents via RAG (in-memory or Qdrant) |
| **Draft updates** | Generate consequence-first stakeholder updates with severity-based cadence (SEV1=5min, SEV2=15min, SEV3=30min) |
| **Suggest remediation** | Pattern-match past incidents, suggest actions with citations and confidence scores |
| **Dry-run simulate** | LLM predicts the expected outcome of each suggested remediation |
| **Generate postmortem** | COE-format postmortem with AI-labeled sections, severity-conditional (SEV1=8 sections, SEV2=6, SEV3=5) |
| **Track costs** | Per-node LLM cost tracking with JSONL observability log |
| **Export** | 10 output files: summary, timeline, updates, comms blocks, remediation, postmortem, cost report, LLM calls, session, meta |

---

## CLI Commands

```bash
# Simulate an incident (no input data needed)
incident-commander simulate --service payment-service --severity SEV1 --output-dir ./output/
incident-commander simulate --scenario db-connection-pool --output-dir ./output/

# Run from real data
incident-commander run --alert alert.json --logs ./logs/ --output-dir ./output/
incident-commander run --input-dir ./incident-data/ --output-dir ./output/

# Review saved sessions
incident-commander timeline --thread <thread-id>
incident-commander postmortem --thread <thread-id>

# Export JSON Schemas
incident-commander export-schemas --output-dir ./schemas/

# Validate input
incident-commander validate --alert alert.json

# Auto-approve all interrupts (for CI/pipelines)
incident-commander simulate --auto-approve
```

---

## Python API

```python
from incident_commander import run_simulation, run_incident

# Simulate an incident
result = run_simulation(
    service="payment-service",
    severity="SEV1",
    auto_approve=True,
)

# Run from real data
result = run_incident(
    alert={"severity": "SEV1", "service": "api-gateway", ...},
    logs=[{"timestamp": "...", "level": "ERROR", "message": "..."}],
    messages=[{"timestamp": "...", "author": "alice", "text": "..."}],
    auto_approve=True,
)

print(result.postmortem.root_cause_analysis.content)
print(f"Cost: ${result.cost_report.total_estimated_cost_usd:.4f}")
```

---

## Input Directory

Structured directory for batch processing:

```
incident-data/
├── meta.json                 # incident_id, service, severity, start_time
├── alert.json                # Required: severity, service, summary, source, timestamp
├── logs/                     # Optional: .log, .json, or .md files
│   ├── 01-app.log
│   └── 02-database.json
├── messages.json             # Optional: chat messages
├── github.json               # Optional: GitHub PRs
├── runbooks/                 # Optional: runbook JSON files
└── notes.md                  # Optional: manual event notes (## headings → timeline)
```

---

## Output Directory

10 files per run:

```
output/
├── incident-summary.md       # ID, service, severity, MTTR, cost
├── timeline.md               # Chronological event table with trust levels
├── stakeholder-updates.md    # Consequence-first update drafts
├── comms-blocks.md           # Pasteable Slack/email blocks
├── remediation.md            # Suggested actions with citations
├── postmortem.md             # COE-format postmortem with AI labels
├── cost-report.md            # Per-node LLM cost breakdown
├── llm-calls.jsonl           # Raw LLM call log (response text)
├── session.json              # Full session state
└── meta.json                 # Session metadata
```

---

## Configuration

The tool uses environment variables for LLM configuration:

```bash
# Default: Ollama local
export LLM_MODEL=ollama/qwen2.5-coder:7b
export LLM_BASE_URL=http://localhost:11434/v1

# Or: OpenCode Zen (cloud, cheap)
export LLM_MODEL=deepseek-v4-flash
export LLM_BASE_URL=https://opencode.ai/zen/v1
export LLM_API_KEY=<your-key>

# Or: OpenAI
export LLM_MODEL=gpt-4o-mini
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_API_KEY=<your-key>
```

Full config options (set via Python API):

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `"simulate"` | `"simulate"` auto-approves interrupts; `"run"` requires human approval |
| `analysis_model` | `"ollama/qwen2.5-coder:7b"` | Primary LLM for root-cause analysis |
| `comms_model` | `None` | LLM for stakeholder updates (falls back to analysis_model) |
| `postmortem_model` | `None` | LLM for postmortem generation (falls back to analysis_model) |
| `confidence_threshold` | `0.7` | Minimum confidence for remediation suggestions |
| `deploy_correlation_window` | `30` | Minutes before alert to check for deploy correlations |
| `cadence` | `{"SEV1": 5, "SEV2": 15, "SEV3": 30}` | Stakeholder update intervals by severity |
| `qdrant_url` | `None` | Qdrant vector DB URL (None = in-memory retriever) |
| `session_dir` | `~/.incident-commander/sessions` | Session persistence directory |
| `output_format` | `"markdown"` | Output format (`"markdown"` or `"json"`) |

---

## Simulation Scenarios

| Scenario | Service | Severity | Deploy Correlated |
|----------|---------|----------|-------------------|
| `db-connection-pool` | payment-service | SEV1 | ✅ |
| `bad-deploy` | api-gateway | SEV2 | ✅ |
| `memory-leak` | auth-service | SEV2 | ❌ |
| `cert-expiry` | api-gateway | SEV1 | ❌ |
| `dependency-outage` | payment-service | SEV1 | ❌ |
| `config-drift` | web-frontend | SEV3 | ✅ |
| `cache-invalidation` | product-catalog | SEV2 | ❌ |
| `rate-limit-hit` | search-service | SEV3 | ❌ |

---

## Safety Guardrails

| Guardrail | What it does |
|-----------|-------------|
| **Interrupt points** | 3 human-in-the-loop gates: stakeholder update, remediation review, postmortem review. Auto-approve with `--auto-approve` for CI |
| **Confidence threshold** | Remediation suggestions below 0.7 confidence are suppressed (configurable) |
| **Source citations** | Every remediation must cite a runbook or past incident. Suggestions without citations are rejected |
| **Dry-run only** | LLM simulates remediation outcomes as text — never executes production changes |
| **Blameless framing** | Postmortem prompts enforce blameless language (COE format) |
| **AI section labels** | All AI-generated content is labeled `[AI-GENERATED — review carefully]` |
| **Graceful degradation** | LLM failures produce fallback "insufficient data" content — never crashes the graph |

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Input Dir   │     │  CLI Flags   │     │  Python API  │
│  (files)     │     │  (args)      │     │  (program)   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Normalizer    │
                    │  (obj/dict/path│
                    │   → Pydantic)  │
                    └───────┬────────┘
                            │
                    ┌───────▼─────────────────────┐
                    │     LangGraph StateGraph     │
                    │                              │
                    │  receive_alert → build_      │
                    │  timeline → correlate_       │
                    │  deploys → retrieve_runbooks │
                    │  → rerank → cadence_timer →  │
                    │  draft_update → [APPROVE] →  │
                    │  produce_output → ... →      │
                    │  resolve → suggest_          │
                    │  remediation → dry_run →     │
                    │  [APPROVE] → generate_        │
                    │  postmortem → [APPROVE] →    │
                    │  cost_report → END           │
                    └───────┬──────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  10 output     │
                    │  markdown files│
                    └────────────────┘
```

---

## Documentation

- [Product Requirements](docs/PRD.md)
- [Technical Specification](docs/SPEC.md)
- [Work Breakdown Structure](docs/wbs.md)
- [API Reference](docs/api-reference.md) *(coming soon)*
- [Safety Guardrails](docs/safety-guardrails.md) *(coming soon)*
- [Simulation Guide](docs/simulation-guide.md) *(coming soon)*
- [Input Format](docs/input-format.md) *(coming soon)*
- [Output Format](docs/output-format.md) *(coming soon)*

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check
mypy --strict src/
```

---

## License

MIT
