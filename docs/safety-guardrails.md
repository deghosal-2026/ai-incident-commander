# Safety Guardrails

ai-incident-commander is designed as an **advisory** system — it drafts,
suggests, and simulates, but never executes. This document catalogs every
safety constraint enforced in the codebase, the three human-in-the-loop
interrupt gates, and the architectural guarantee that the system has no
execution capability.

All references below cite the exact source locations for verification.

---

## Safety Constraints Summary

| # | Guardrail | Enforced in | Mechanism |
|---|-----------|-------------|-----------|
| 1 | Human approval required for stakeholder updates | `stakeholder.py:168` | `interrupt_for_approval` gate |
| 2 | Human approval required for remediation | `remediation.py:220` | `interrupt_for_remediation_review` gate |
| 3 | Human approval required for postmortem | `postmortem.py:245` | `interrupt_for_postmortem_review` gate |
| 4 | Remediation citations mandatory | `remediation.py:106` | Reject suggestions lacking a citation |
| 5 | Confidence threshold suppresses low-confidence suggestions | `remediation.py:140` | Configurable threshold, default 0.7 |
| 6 | Dry-run is text prediction, NOT code execution | `remediation.py:183,197` | LLM prompt only; no execution path |
| 7 | Blameless postmortem rules | `postmortem.py:50` | Enforced in the LLM prompt |
| 8 | AI-generated sections labelled | `formatters.py:127` | `ai_generated` flag + markdown tags |
| 9 | No execution nodes in the graph | `graph.py` (architecture) | No node touches production systems |
| 10 | Simulate mode is the safe default | `config.py:39`, `state.py:256` | `mode` defaults to `"simulate"` |

---

## 1. Human-in-the-Loop Interrupt Gates

The graph pauses at three points for human review. In **simulate mode**, all
three gates auto-approve (the system runs end-to-end without pausing). In
**run mode**, each gate pauses via the LangGraph interrupt mechanism and
requires a human to approve or reject before the graph resumes.

### Interrupt Point 1: Stakeholder Update Review

- **Node:** `interrupt_for_approval` (`stakeholder.py:168`)
- **Preceded by:** `draft_update_node` — generates a consequence-first update
- **Followed by (approved):** `produce_output_node` — finalizes and sends the update
- **Followed by (rejected):** loops back to `draft_update_node` for redrafting

**What happens here:**
The LLM has drafted a stakeholder update in consequence-first format
(IMPACT / ROOT_CAUSE / ACTION / CONFIDENCE). Before this draft reaches
stakeholders, a human reviews it for:
- Factual accuracy of the impact assessment
- Appropriateness of the root-cause hypothesis
- Correctness of the stated action

The draft is stored in `state.current_update_draft` and **not** marked as
approved. Only after the human sets `update_approved = True` does
`produce_output_node` append the draft to `state.stakeholder_updates` (the
sent list) and update `last_update_time`.

If rejected, the graph loops back to `draft_update_node` to generate a new
draft with the same context.

### Interrupt Point 2: Remediation Review

- **Node:** `interrupt_for_remediation_review` (`remediation.py:220`)
- **Preceded by:** `suggest_remediation_node` → `dry_run_simulate_node`
- **Followed by (approved):** `generate_postmortem_node`
- **Followed by (rejected):** loops back to `suggest_remediation_node`

**What happens here:**
The LLM has proposed ONE remediation action with a source citation, a
confidence score, and a dry-run outcome prediction. A human reviews:
- Whether the suggested action is safe and appropriate
- Whether the citation (runbook or past incident) is valid and relevant
- Whether the dry-run outcome prediction makes sense
- Whether the confidence level justifies actioning the suggestion

On approval, the suggestion is appended to
`state.remediation_suggestions` and `remediation_approved` is set to `True`.
On rejection, the graph loops back to generate a new suggestion.

### Interrupt Point 3: Postmortem Review

- **Node:** `interrupt_for_postmortem_review` (`postmortem.py:245`)
- **Preceded by:** `generate_postmortem_node`
- **Followed by (approved):** `cost_report_node` → `END`
- **Followed by (rejected):** loops back to `generate_postmortem_node`

**What happens here:**
The LLM has generated a COE-format postmortem with blameless framing and
AI-section labels. A human reviews:
- Blameless compliance (no individual names in root cause or systemic factors)
- Factual accuracy of the timeline and root cause analysis
- Completeness and appropriateness of action items
- Correctness of severity-conditional sections

On approval, `postmortem_approved` is set to `True` and the graph proceeds to
cost aggregation and termination. On rejection, the graph loops back to
regenerate the postmortem with adjustments.

---

## 2. Confidence Threshold

### Default and configuration

- **Default value:** `0.7` (70% confidence)
- **Configured via:** `Config.confidence_threshold` (`config.py:54`)
- **Range:** `0.0` to `1.0` (validated by Pydantic `Field(ge=0.0, le=1.0)`)
- **Read by:** `_get_threshold()` in `remediation.py:36`

```python
# config.py
confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

# remediation.py
def _get_threshold() -> float:
    if _config is not None:
        return _config.confidence_threshold
    return 0.7  # Conservative default if config not initialized
```

### How it works

In `suggest_remediation_node` (`remediation.py:140`), after the LLM returns a
remediation suggestion, the node checks whether the suggestion's confidence
meets the threshold:

- If `confidence >= threshold`: the suggestion is surfaced to the human
  reviewer.
- If `confidence < threshold`: the suggestion is **suppressed** and replaced
  with `"No suggestion — confidence below threshold"`. The original confidence
  value is preserved in the suppressed `RemediationSuggestion` for auditability.

This guardrail ensures low-probability remediation actions never waste the
incident commander's time or cause harm. The threshold check is skipped only
when the suggestion was already rejected for a missing citation (since a
rejected suggestion has `citation=""` and is not actionable regardless).

### Tuning

To make the system more conservative (surface fewer suggestions), raise the
threshold:

```python
from incident_commander.config import Config

config = Config(confidence_threshold=0.85)  # only show 85%+ confidence
```

To make it more permissive, lower it:

```python
config = Config(confidence_threshold=0.5)  # show 50%+ confidence
```

Setting it to `0.0` disables suppression entirely (all cited suggestions are
surfaced). Setting it to `1.0` requires perfect confidence (effectively
suppresses everything unless the LLM reports 1.0).

---

## 3. Dry-Run Explanation — LLM Simulation, NOT Code Execution

### What dry-run is

`dry_run_simulate_node` (`remediation.py:197`) asks the LLM to **predict in
text** what would happen if the proposed remediation action were taken. The
prompt instructs the LLM to produce a brief prediction, for example:

> "payment success rate should return to >99% within 2 minutes of rollback"

The prediction is stored in `current_remediation.dry_run_outcome` and shown
to the human reviewer at the remediation review gate.

### What dry-run is NOT

The dry-run is **text prediction only**. The architecture has:

- **No shell execution** — the LLM never runs commands
- **No API calls** — no HTTP requests are made to production systems
- **No code execution** — no scripts are invoked
- **No state mutation** — no configuration, infrastructure, or services are
  touched

This is enforced architecturally: `dry_run_simulate_node` calls
`router.generate(prompt, task="analysis")`, which performs a single HTTP POST
to an OpenAI-compatible LLM endpoint and returns text. There is no code path
from this node to any production system.

The prompt explicitly frames the task as prediction:

```
You are an incident simulator. Predict the expected outcome of a
remediation action.
...
Format your response as a brief prediction of what would happen if this
action is taken.
```

---

## 4. AI Section Labeling Convention

### Provenance tracking

Every `PostmortemSection` and `ActionItem` carries an `ai_generated` boolean
flag (`state.py:130`, `state.py:139`):

- `ai_generated=True` — the LLM authored this content
- `ai_generated=False` — a human authored/edited it, or it was reconstructed
  from structured session data

### How sections are labelled

In `generate_postmortem_node` (`postmortem.py:155-174`):

| Section | `ai_generated` | Rationale |
|---------|----------------|-----------|
| Summary | `True` | LLM-authored |
| Customer Impact | `True` | LLM-authored |
| Timeline | `False` | Reconstructed from structured state data, not LLM hallucination |
| Root Cause Analysis | `True` | LLM-authored |
| Systemic Contributing Factors | `True` | LLM-authored |
| Action Items | `True` (per item) | LLM-authored |
| Stakeholder Communication Log | `False` | From structured session data |
| Regulatory/Compliance Impact | `True` | LLM-authored |

### Markdown rendering

In `formatters.py:121-138`, the `_section_md()` function appends a provenance
tag to each section header:

- AI-authored sections: ` *[AI-GENERATED — review carefully]*`
- Session-data sections: ` *[From session data]*`

Action items are individually tagged with ` *[AI-generated]*`.

### AI Section Labels summary table

The formatted postmortem ends with a provenance summary table
(`formatters.py:194-218`):

```
### AI Section Labels
| Section | Source |
|---------|--------|
| Summary | AI-generated |
| Timeline | Session data |
| Root Cause Analysis | AI-generated |
| Systemic Factors | AI-generated |
...
```

This ensures a human reviewer can immediately see which sections require
scrutiny (AI-generated) versus which are grounded in verifiable session data.

---

## 5. Blameless Postmortem Rules

Blameless rules are enforced **in the LLM prompt** in
`_build_postmortem_prompt()` (`postmortem.py:57-60`):

```
BLAMELESS RULES (SAFETY GUARDRAIL):
- Focus on what failed, not who failed.
- Systemic Contributing Factors must focus on processes, not people.
- Do not include individual names in root cause or systemic factors.
```

### What this means

1. **What failed, not who failed** — The postmortem must describe the
   technical or process failure, not attribute blame to a person.
2. **Systemic factors focus on processes** — The "Systemic Contributing
   Factors" section must address broken processes, missing safeguards, or
   tooling gaps — not individual mistakes.
3. **No individual names in root cause or systemic factors** — The LLM is
   explicitly instructed to omit personal names from these sections.

### Enforcement

These rules are enforced via prompt engineering, not post-hoc filtering. The
LLM is instructed at generation time to follow blameless framing. The
`interrupt_for_postmortem_review` gate provides a second layer of defense:
a human reviewer can reject the postmortem if blameless compliance is
violated, causing the graph to regenerate it.

### Action items with suggested owners

Action items do include a `suggested_owner` field (`state.py:137`), but this
is a **team or role recommendation** (e.g. "Payments Team", "SRE"), not an
individual blame attribution. The prompt asks for "suggested owner" in the
context of corrective action assignment, not fault assignment.

---

## 6. No Execution Capability

### Architectural guarantee

The ai-incident-commander graph contains **no execution nodes**. The 14
nodes in the graph perform only these operations:

1. **Data fusion** — merge input sources into a timeline (`build_timeline`,
   `correlate_deploys`)
2. **Retrieval** — fetch and rerank runbooks/evidence (`retrieve_runbooks`,
   `rerank_evidence`)
3. **LLM generation** — draft text via LLM calls (`draft_update`,
   `suggest_remediation`, `dry_run_simulate`, `generate_postmortem`)
4. **Human gates** — pause for approval (`interrupt_for_approval`,
   `interrupt_for_remediation_review`, `interrupt_for_postmortem_review`)
5. **State finalization** — move drafts to sent lists (`produce_output`)
6. **Cost aggregation** — sum token costs (`cost_report`)

### What the system cannot do

- **Cannot run shell commands** — no node invokes `subprocess`, `os.system`,
  or any command runner
- **Cannot make production API calls** — the only outbound HTTP is to the LLM
  endpoint (OpenAI-compatible), and optionally to Qdrant/GitHub for read-only
  retrieval
- **Cannot modify infrastructure** — no Terraform, Kubernetes, or cloud SDK
  calls
- **Cannot deploy or rollback** — remediation suggestions are text proposals
  that a human must action manually
- **Cannot send stakeholder updates** — drafts are produced; a human approves
  and sends them through external channels

### The dry-run boundary

The closest the system comes to "action" is `dry_run_simulate_node`, which
produces a **text prediction** of an action's outcome. This is explicitly a
prompt to the LLM asking "what would happen if..." — it never performs the
action. See §3 above.

---

## 7. Simulate Mode as the Safe Default

`Config.mode` defaults to `"simulate"` (`config.py:39`) and `IncidentState.mode`
defaults to `"simulate"` (`state.py:256`). This means:

- All three interrupt gates auto-approve without pausing
- The incident is marked resolved after the first stakeholder update
  (`produce_output_node`, `stakeholder.py:162`)
- The graph runs end-to-end without human intervention

This is the safe default for demos, testing, and CI. To require human
approval at every gate, set `mode="run"`:

```python
config = Config(mode="run")
```

or via the CLI:

```bash
incident-commander simulate --severity SEV1   # defaults to run mode (no --auto-approve)
```

The `--auto-approve` CLI flag sets `mode="simulate"` to bypass gates for
testing.
