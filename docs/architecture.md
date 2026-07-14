# Architecture

This document describes the internal architecture of **ai-incident-commander**:
the LangGraph state graph, the `IncidentState` lifecycle, per-node contracts,
LLM routing, cost tracking, and session persistence.

All details below are derived from the source code in
`src/incident_commander/`.

---

## High-Level Data Flow

```
                         ┌─────────────┐
                         │  Input data │  (alert, logs, messages, PRs, runbooks)
                         └──────┬──────┘
                                │
                                ▼
              ┌──────────────────────────────────────┐
              │          IncidentState               │   (Pydantic schema)
              │  alert · input_logs · input_messages │
              │  input_prs · input_manual_events     │
              └─────────────────┬────────────────────┘
                                │
                                ▼
            ┌───────────────────────────────────────┐
            │         LangGraph StateGraph          │
            │  (14 nodes · 4 conditional edges)     │
            └─────────────────┬─────────────────────┘
                              │
   ┌──────────────────────────┼───────────────────────────┐
   │                          │                           │
   ▼                          ▼                           ▼
 Timeline &            Stakeholder comms            Remediation &
 deploy correlation    (cadence-driven loop)         postmortem
   │                          │                           │
   └──────────────┬───────────┴───────────┬───────────────┘
                  ▼                       ▼
            ┌──────────┐            ┌───────────┐
            │ CostReport│           │  Postmortem│
            └──────┬─────┘           └─────┬─────┘
                   │                       │
                   ▼                       ▼
              ┌─────────────────────────────────┐
              │   SessionManager (JSON on disk) │
              │   ~/.incident-commander/sessions │
              └─────────────────────────────────┘
```

---

## LangGraph Graph Visualization

The graph is built by `build_graph()` in `src/incident_commander/graph.py`.
It registers **14 nodes** across 6 phases and wires **4 conditional edges**
plus the linear edges shown below.

```
                            ENTRY POINT
                                │
                                ▼
                       ┌─────────────────┐
                       │ build_timeline  │   Phase 1: Data fusion
                       └────────┬────────┘
                                │
                                ▼
                     ┌────────────────────┐
                     │ correlate_deploys  │
                     └─────────┬──────────┘
                               │
                               ▼
                     ┌──────────────────┐
                     │ retrieve_runbooks│   Phase 2: RAG retrieval
                     └─────────┬────────┘
                               │
                               ▼
                     ┌─────────────────┐
                     │ rerank_evidence │
                     └────────┬────────┘
                              │
                              ▼
                     ┌───────────────┐
              ┌─────►│ cadence_timer │   Phase 3: Stakeholder comms
              │      └───────┬───────┘
              │              │
              │              ▼
              │      ┌─────────────┐
              │      │ draft_update│
              │      └──────┬──────┘
              │             │
              │             ▼
              │   ┌─────────────────────────┐
              │   │ interrupt_for_approval  │ ◄── CONDITIONAL EDGE 1
              │   └──────────┬──────────────┘
              │     approved  │  \  rejected
              │          │    │   \    │
              │          │    │    └───┴──► (back to draft_update)
              │          ▼    │
              │   ┌───────────────┐
              │   │ produce_output│ ◄── CONDITIONAL EDGE 2
              │   └───────┬───────┘
              │     resolved │  \  not resolved
              │       (remediate) \ (continue)
              │           │       └──────► (back to cadence_timer)
              │           ▼
              │  ┌──────────────────────┐
              │  │ suggest_remediation  │   Phase 4: Remediation
              │  └──────────┬───────────┘
              │             │
              │             ▼
              │  ┌────────────────────┐
              │  │ dry_run_simulate   │
              │  └─────────┬──────────┘
              │            │
              │            ▼
              │  ┌─────────────────────────────────────┐
              │  │ interrupt_for_remediation_review    │ ◄── CONDITIONAL EDGE 3
              │  └──────────┬──────────────────────────┘
              │    approved  │  \  rejected
              │         │    │   \    │
              │         │    │    └───┴──► (back to suggest_remediation)
              │         ▼    │
              │  ┌───────────────────────┐
              │  │ generate_postmortem   │   Phase 5: Postmortem
              │  └──────────┬────────────┘
              │             │
              │             ▼
              │  ┌────────────────────────────────────┐
              │  │ interrupt_for_postmortem_review    │ ◄── CONDITIONAL EDGE 4
              │  └──────────┬─────────────────────────┘
              │    approved  │  \  rejected
              │         │    │   \    │
              │         │    │    └───┴──► (back to generate_postmortem)
              │         ▼    │
              │  ┌──────────────┐
              │  │  cost_report │   Phase 6: Cost aggregation
              │  └──────┬───────┘
              │         │
              │         ▼
              │       ┌───┐
              │       │END│
              │       └───┘
```

### Edge inventory

| # | From | To | Type | Router function |
|---|------|----|------|-----------------|
| 1 | `build_timeline` | `correlate_deploys` | linear | — |
| 2 | `correlate_deploys` | `retrieve_runbooks` | linear | — |
| 3 | `retrieve_runbooks` | `rerank_evidence` | linear | — |
| 4 | `rerank_evidence` | `cadence_timer` | linear | — |
| 5 | `cadence_timer` | `draft_update` | linear | — |
| 6 | `draft_update` | `interrupt_for_approval` | linear | — |
| 7 | `interrupt_for_approval` | `produce_output` / `draft_update` | **conditional** | `_approval_router` |
| 8 | `produce_output` | `suggest_remediation` / `cadence_timer` | **conditional** | `_is_resolved` |
| 9 | `suggest_remediation` | `dry_run_simulate` | linear | — |
| 10 | `dry_run_simulate` | `interrupt_for_remediation_review` | linear | — |
| 11 | `interrupt_for_remediation_review` | `generate_postmortem` / `suggest_remediation` | **conditional** | `_remediation_router` |
| 12 | `generate_postmortem` | `interrupt_for_postmortem_review` | linear | — |
| 13 | `interrupt_for_postmortem_review` | `cost_report` / `generate_postmortem` | **conditional** | `_postmortem_router` |
| 14 | `cost_report` | `END` | linear | — |

**Entry point:** `build_timeline`
**Terminal node:** `cost_report` → `END`

> Note: The module docstring in `graph.py` mentions "15 nodes" but the code
> registers **14** nodes (confirmed by the inline comment
> `Register all 14 nodes` at `graph.py:170`).

---

## State Transitions — IncidentState Lifecycle

`IncidentState` (`src/incident_commander/models/state.py`) is the single
Pydantic state object threaded through every node. Every field has a sensible
default so `IncidentState()` is valid at any point in the lifecycle. Nodes are
responsible for populating only the fields they own.

### Lifecycle stages

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  STAGE 1 — INPUT LOADING  (build_and_run, graph.py:276)                 │
 │  alert, severity, service, incident_id, thread_id, mode set             │
 │  input_logs, input_messages, input_prs, input_manual_events populated   │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  STAGE 2 — DATA FUSION  (build_timeline, correlate_deploys)             │
 │  timeline: list[TimelineEvent]            ← merged chronological events │
 │  deploy_correlations: list[DeployCorrelation] ← PRs correlated to alert │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  STAGE 3 — RAG RETRIEVAL  (retrieve_runbooks, rerank_evidence)          │
 │  retrieved_runbooks: list[dict]     ← matched runbooks                  │
 │  retrieved_incidents: list[dict]    ← past incidents                    │
 │  reranked_evidence: list[dict]      ← post-rerank top-k                 │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  STAGE 4 — STAKEHOLDER COMMS LOOP  (cadence → draft → approve → output) │
 │  next_update_time: datetime          ← set by cadence_timer_node        │
 │  current_update_draft: StakeholderUpdate | None  ← draft_update_node    │
 │  update_approved: bool               ← toggled by interrupt gate        │
 │  stakeholder_updates: list[StakeholderUpdate]   ← produce_output_node   │
 │  last_update_time: datetime          ← updated on each send             │
 │  resolved: bool                      ← True in simulate after 1st send  │
 │     ┌──────────────────────────────────────────────────┐                │
 │     │  LOOPS back to cadence_timer when not resolved   │                │
 │     └──────────────────────────────────────────────────┘                │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │ resolved == True
                                ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  STAGE 5 — REMEDIATION  (suggest → dry-run → review)                    │
 │  current_remediation: RemediationSuggestion | None  ← suggest node      │
 │  current_remediation.dry_run_outcome: str           ← dry_run node      │
 │  remediation_approved: bool                         ← review gate       │
 │  remediation_suggestions: list[RemediationSuggestion] ← on approve      │
 │     ┌──────────────────────────────────────────────────┐                │
 │     │  LOOPS back to suggest_remediation on rejection  │                │
 │     └──────────────────────────────────────────────────┘                │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │ remediation_approved == True
                                ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  STAGE 6 — POSTMORTEM  (generate → review)                              │
 │  postmortem: Postmortem | None          ← generate_postmortem_node      │
 │  postmortem_approved: bool              ← review gate                   │
 │     ┌──────────────────────────────────────────────────┐                │
 │     │  LOOPS back to generate_postmortem on rejection  │                │
 │     └──────────────────────────────────────────────────┘                │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │ postmortem_approved == True
                                ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  STAGE 7 — COST AGGREGATION  (cost_report_node)                         │
 │  cost_report: CostReport | None         ← aggregated from CostTracker   │
 └─────────────────────────────────────────────────────────────────────────┘
```

### IncidentState field reference

| Field | Type | Default | Set by |
|-------|------|---------|--------|
| `alert` | `Alert \| None` | `None` | input loading |
| `severity` | `Literal["SEV1","SEV2","SEV3"]` | `"SEV3"` | input loading (mirrors alert) |
| `service` | `str` | `""` | input loading (mirrors alert) |
| `incident_id` | `str` | `""` | input loading (mirrors alert) |
| `input_logs` | `list[LogEntry]` | `[]` | input loading |
| `input_messages` | `list[ChatMessage]` | `[]` | input loading |
| `input_prs` | `list[GitHubPR]` | `[]` | input loading |
| `input_manual_events` | `list[TimelineEvent]` | `[]` | input loading |
| `timeline` | `list[TimelineEvent]` | `[]` | `build_timeline_node` |
| `deploy_correlations` | `list[DeployCorrelation]` | `[]` | `correlate_deploys_node` |
| `retrieved_runbooks` | `list[dict]` | `[]` | `retrieve_runbooks_node` |
| `retrieved_incidents` | `list[dict]` | `[]` | `retrieve_runbooks_node` |
| `reranked_evidence` | `list[dict]` | `[]` | `rerank_evidence_node` |
| `stakeholder_updates` | `list[StakeholderUpdate]` | `[]` | `produce_output_node` |
| `current_update_draft` | `StakeholderUpdate \| None` | `None` | `draft_update_node` |
| `update_approved` | `bool` | `False` | `interrupt_for_approval` |
| `remediation_suggestions` | `list[RemediationSuggestion]` | `[]` | `interrupt_for_remediation_review` |
| `current_remediation` | `RemediationSuggestion \| None` | `None` | `suggest_remediation_node` |
| `remediation_approved` | `bool` | `False` | `interrupt_for_remediation_review` |
| `postmortem` | `Postmortem \| None` | `None` | `generate_postmortem_node` |
| `postmortem_approved` | `bool` | `False` | `interrupt_for_postmortem_review` |
| `cost_report` | `CostReport \| None` | `None` | `cost_report_node` |
| `thread_id` | `str` | `""` | input loading (LangGraph checkpoint key) |
| `mode` | `Literal["simulate","run"]` | `"simulate"` | input loading |
| `resolved` | `bool` | `False` | `produce_output_node` (simulate) or human (run) |
| `last_update_time` | `datetime \| None` | `None` | `produce_output_node` |
| `next_update_time` | `datetime \| None` | `None` | `cadence_timer_node` |

---

## Node Descriptions (Inputs / Outputs)

### Phase 1 — Data fusion

#### `build_timeline_node`
- **File:** `src/incident_commander/nodes/timeline.py`
- **Reads:** `alert`, `input_logs`, `input_messages`, `input_prs`, `input_manual_events`
- **Writes:** `timeline` (merged, chronological `list[TimelineEvent]`)
- **Purpose:** Fuses multi-source inputs (alert, chat, logs, GitHub PRs, manual events) into a single unified, chronologically-ordered timeline. Each event carries a `source` tag and `trust_level`.

#### `correlate_deploys_node`
- **File:** `src/incident_commander/nodes/deploy_correlation.py`
- **Reads:** `input_prs`, `alert.timestamp`, `deploy_correlation_window_minutes` (config, default 30 min)
- **Writes:** `deploy_correlations` (`list[DeployCorrelation]`)
- **Purpose:** Identifies GitHub PRs merged within the look-back window before the alert. Each correlation records `pr_number`, `pr_title`, `author`, `merge_time`, `files_changed`, `minutes_before_alert`, and `correlation_strength` (`"strong"` or `"weak"`).

### Phase 2 — RAG retrieval

#### `retrieve_runbooks_node`
- **File:** `src/incident_commander/nodes/rag.py`
- **Reads:** `timeline`, `service`, `severity`, runbooks (from `InMemoryRetriever` or Qdrant)
- **Writes:** `retrieved_runbooks`, `retrieved_incidents`
- **Purpose:** Retrieves relevant runbooks and historical incidents via keyword/semantic matching. Uses `InMemoryRetriever` by default; a Qdrant-backed retriever is used when `qdrant_url` is configured.

#### `rerank_evidence_node`
- **File:** `src/incident_commander/nodes/rerank.py`
- **Reads:** `retrieved_runbooks`, `retrieved_incidents`
- **Writes:** `reranked_evidence` (post-rerank top-k `list[dict]`)
- **Purpose:** Reranks retrieved evidence by relevance to produce the top-k items used downstream by the comms and remediation nodes.

### Phase 3 — Stakeholder communication

#### `cadence_timer_node`
- **File:** `src/incident_commander/nodes/cadence.py`
- **Reads:** `severity`, `last_update_time`, `cadence` config dict (`SEV1: 5`, `SEV2: 15`, `SEV3: 30` minutes)
- **Writes:** `next_update_time`
- **Purpose:** Enforces the per-severity update cadence. Decides whether enough time has elapsed since the last update to draft a new one.

#### `draft_update_node`
- **File:** `src/incident_commander/nodes/stakeholder.py:114`
- **Reads:** `alert`, `service`, `severity`, `deploy_correlations`, `retrieved_runbooks`, timeline summary
- **Writes:** `current_update_draft` (`StakeholderUpdate`), sets `update_approved = False`
- **LLM task:** `"comms"`
- **Purpose:** Generates a consequence-first stakeholder update (IMPACT / ROOT_CAUSE / ACTION / CONFIDENCE) via LLM. Includes deploy correlation context and top-3 retrieved runbooks in the prompt.

#### `interrupt_for_approval`
- **File:** `src/incident_commander/nodes/stakeholder.py:168`
- **Reads:** `mode`, `current_update_draft`
- **Writes:** `update_approved`
- **Purpose:** Human-in-the-loop gate. In `simulate` mode, auto-approves. In `run` mode, the LangGraph interrupt mechanism pauses for a human reviewer to approve or reject the draft before it reaches stakeholders.

#### `produce_output_node`
- **File:** `src/incident_commander/nodes/stakeholder.py:136`
- **Reads:** `current_update_draft`, `mode`
- **Writes:** appends to `stakeholder_updates`, updates `last_update_time`, clears `current_update_draft`, sets `update_approved = False`. In `simulate` mode, sets `resolved = True`.
- **Purpose:** Finalizes the approved draft into the sent-updates list. In simulate mode, marks the incident resolved after the first update so the graph exits the comms loop and proceeds to remediation. In run mode, `resolved` stays `False` until a human declares the incident over.

### Phase 4 — Remediation

#### `suggest_remediation_node`
- **File:** `src/incident_commander/nodes/remediation.py:132`
- **Reads:** `alert`, `service`, `reranked_evidence`, `deploy_correlations`, `confidence_threshold` (config)
- **Writes:** `current_remediation` (`RemediationSuggestion`), sets `remediation_approved = False`
- **LLM task:** `"analysis"`
- **Purpose:** Proposes ONE remediation action with a mandatory source citation. Enforces two safety guardrails: (1) suggestions without a citation are rejected, (2) suggestions below the confidence threshold (default 0.7) are suppressed.

#### `dry_run_simulate_node`
- **File:** `src/incident_commander/nodes/remediation.py:197`
- **Reads:** `current_remediation`, `alert`, `service`
- **Writes:** `current_remediation.dry_run_outcome`
- **LLM task:** `"analysis"`
- **Purpose:** LLM generates a **text prediction** of what would happen if the proposed action is taken. This is NOT code execution — the LLM never runs shell commands, makes API calls, or touches production systems.

#### `interrupt_for_remediation_review`
- **File:** `src/incident_commander/nodes/remediation.py:220`
- **Reads:** `mode`, `current_remediation`
- **Writes:** `remediation_approved`, appends to `remediation_suggestions` (on approve)
- **Purpose:** Human-in-the-loop gate. In `simulate` mode, auto-approves and appends the suggestion to the list. In `run` mode, pauses for a human to evaluate the suggestion and its dry-run outcome before actioning.

### Phase 5 — Postmortem

#### `generate_postmortem_node`
- **File:** `src/incident_commander/nodes/postmortem.py:214`
- **Reads:** `incident_id`, `service`, `severity`, `alert.timestamp`, `timeline`, `stakeholder_updates`, `reranked_evidence`
- **Writes:** `postmortem` (`Postmortem`), sets `postmortem_approved = False`
- **LLM task:** `"postmortem"`
- **Purpose:** Generates an Amazon COE-format postmortem with severity-conditional sections:
  - **SEV1:** all 8 sections (summary, customer_impact, timeline, root_cause_analysis, systemic_contributing_factors, action_items, stakeholder_communication_log, regulatory_compliance_impact)
  - **SEV2:** omits regulatory_compliance_impact + stakeholder_communication_log
  - **SEV3:** omits customer_impact + regulatory_compliance_impact + stakeholder_communication_log
  - Enforces blameless rules in the prompt and labels AI-generated sections via `ai_generated` flags. Computes MTTR as `(last_timeline_event - alert.timestamp)` in minutes.

#### `interrupt_for_postmortem_review`
- **File:** `src/incident_commander/nodes/postmortem.py:245`
- **Reads:** `mode`, `postmortem`
- **Writes:** `postmortem_approved`, sets `postmortem.approved = True` (on approve)
- **Purpose:** Human-in-the-loop gate. In `simulate` mode, auto-approves. In `run` mode, pauses for a human to check blameless compliance and factual accuracy before publishing.

### Phase 6 — Cost aggregation

#### `cost_report_node`
- **File:** `src/incident_commander/nodes/cost_report.py:14`
- **Reads:** `thread_id`, `LLMRouter.cost_tracker` (module-level singleton)
- **Writes:** `cost_report` (`CostReport`)
- **Purpose:** Aggregates all per-node `NodeCost` records accumulated during the session into a single `CostReport` and stores it in state. This is the terminal node before `END`.

---

## LLM Router Data Flow

The `LLMRouter` (`src/incident_commander/llm_router.py`) is the single entry
point for all LLM calls. It selects the model per **task type**, tracks cost,
and logs every call for observability.

```
   Node calls router.generate(prompt, task=...)
                    │
                    ▼
        ┌───────────────────────┐
        │  _resolve_model(task) │
        └───────────┬───────────┘
                    │
     ┌──────────────┼──────────────────┐
     │ task="comms" │ task="postmortem"│ default
     │  & comms_    │  & postmortem_   │
     │  model set   │  model set       │
     ▼              ▼                  ▼
  comms_model   postmortem_model   analysis_model
  comms_base_url postmortem_base   analysis_base_url
                    │
                    ▼
        ┌───────────────────────────┐
        │  OpenAI-compatible POST   │
        │  {base_url}/chat/completions│
        │  (or mock_llm if provided) │
        └─────────────┬─────────────┘
                      │
         ┌────────────┼─────────────┐
         ▼            ▼             ▼
   ┌──────────┐ ┌───────────┐ ┌──────────────┐
   │CostTracker│ │LLMObserver│ │  info dict   │
   │record_call│ │ log_call  │ │ (model,      │
   │           │ │ → JSONL   │ │  tokens,     │
   └─────┬────┘ └─────┬─────┘ │  cost, latency│
         │            │        │  call_id,    │
         │            │        │  error)      │
         ▼            ▼        └──────┬───────┘
   per-node       ~/.incident-        │
   NodeCost       commander/logs/     │
   list           llm-calls.jsonl     │
                                        ▼
                              returned to node as
                              (response, info)
```

### Task → model resolution (`_resolve_model`)

| Task | Model used | Fallback |
|------|-----------|----------|
| `"analysis"` | `llm.analysis_model` | — (always used as base) |
| `"comms"` | `llm.comms_model` (if set) | falls back to `analysis_model` |
| `"postmortem"` | `llm.postmortem_model` (if set) | falls back to `analysis_model` |

This allows a single-model setup (only `analysis_model` configured) while
still supporting differentiated routing in production — e.g. a powerful model
for analysis and a cheaper model for routine comms.

### `generate()` return contract

`router.generate(prompt, task, model_override=None)` returns a tuple:

```
(response_text: str, info: dict)
```

where `info` contains: `model`, `input_tokens`, `output_tokens`,
`estimated_cost_usd`, `latency_ms`, `call_id`, and `error` (or `None`).

### Node → task mapping

| Node | LLM task |
|------|----------|
| `draft_update_node` | `"comms"` |
| `suggest_remediation_node` | `"analysis"` |
| `dry_run_simulate_node` | `"analysis"` |
| `generate_postmortem_node` | `"postmortem"` |

---

## Cost Tracking Data Flow

Cost tracking is handled by three cooperating components in
`src/incident_commander/llm_router.py`:

```
   Every LLM call (router.generate)
            │
            ├──────────────────────────────────────────┐
            ▼                                          ▼
   ┌────────────────┐                      ┌────────────────────┐
   │  CostTracker   │                      │   LLMObserver      │
   │  (in-memory)   │                      │   (JSONL on disk)  │
   │                │                      │                    │
   │  record_call(  │                      │  log_call(         │
   │    node_name,  │                      │    call_id,        │
   │    model,      │                      │    node_name,      │
   │    input_tok,  │                      │    model, tokens,  │
   │    output_tok, │                      │    cost, latency,  │
   │    cost_usd,   │                      │    prompt_hash,    │
   │    latency_ms) │                      │    error, response)│
   │       │        │                      │       │            │
   │       ▼        │                      │       ▼            │
   │  NodeCost list │                      │  llm-calls.jsonl   │
   └───────┬────────┘                      └────────────────────┘
           │
           │  At graph exit:
           ▼
   ┌──────────────────────┐
   │  cost_report_node    │
   │  get_report(         │
   │    session_id=       │
   │    thread_id)        │
   └──────────┬───────────┘
              ▼
   ┌──────────────────────┐
   │  CostReport          │
   │  · total_input_tokens│
   │  · total_output_tokens│
   │  · total_tokens      │
   │  · total_estimated_  │
   │    cost_usd          │
   │  · per_node: list[   │
   │    NodeCost]         │
   │  · models_used       │
   └──────────┬───────────┘
              ▼
        state.cost_report
```

### Cost estimation (`_estimate_cost`)

Cost is computed from `llm.model_pricing` (per 1M tokens):

```
cost = (input_tokens / 1_000_000 * pricing["input"])
     + (output_tokens / 1_000_000 * pricing["output"])
```

Unknown models default to `{"input": 0.0, "output": 0.0}` (free) so the
cost report never fails due to missing pricing entries. The result is
rounded to 6 decimal places.

### `NodeCost` fields

Each LLM call produces a `NodeCost` record: `node_name`, `llm_model`,
`input_tokens`, `output_tokens`, `total_tokens`, `estimated_cost_usd`,
`latency_ms`.

### `CostReport` fields

The aggregate report (built at graph exit): `session_id`,
`total_input_tokens`, `total_output_tokens`, `total_tokens`,
`total_estimated_cost_usd`, `per_node` (breakdown), `models_used`.

### LLM call observability

`LLMObserver` writes one JSON record per call to
`~/.incident-commander/logs/llm-calls.jsonl`. Each record includes a
`call_id` (12-char hex), timestamp, node name, model, token counts, cost,
latency, SHA-256 `prompt_hash`, error (if any), and a truncated response
(first 2000 chars).

---

## Session Persistence Flow

Session persistence is handled by `SessionManager`
(`src/incident_commander/persistence.py`). Sessions are stored as individual
JSON files named `<thread_id>.json` in the session directory
(`~/.incident-commander/sessions` by default).

```
   Graph execution completes
            │
            ▼
   ┌────────────────────┐
   │  build_and_run()   │   (graph.py:276)
   │  returns state dict │
   └─────────┬──────────┘
             │
             ▼
   ┌────────────────────────────┐
   │  MarkdownOutputWriter      │   (if output_dir provided)
   │  write_all(IncidentResult) │
   └─────────┬──────────────────┘
             │
             ▼
   ┌────────────────────────────────────┐
   │  SessionManager                    │
   │  save_session(thread_id, state)    │
   │  → <thread_id>.json on disk        │
   └────────────────────────────────────┘
```

### SessionManager API

| Method | Purpose |
|--------|---------|
| `save_session(thread_id, state)` | Persist state dict as JSON (uses `default=str` for datetimes/enums) |
| `load_session(thread_id)` | Load and return a session dict; raises `KeyError` if not found, `ValueError` if corrupt |
| `delete_session(thread_id)` | Delete a session file |
| `list_sessions()` | Return sorted list of thread IDs (without `.json` suffix) |
| `export_session(thread_id)` | Alias for `load_session` |
| `get_checkpointer(thread_id)` | Return a `_SessionCheckpointer` for LangGraph checkpointing |

### Checkpointer

`_SessionCheckpointer` provides `get()` and `set()` methods backed by the
`SessionManager`. It caches state in memory and persists checkpoints to disk,
enabling resumable multi-turn incident workflows. `get()` returns the cached
state if available, otherwise loads from disk (returns `{}` if no session
exists).

### Thread ID

`thread_id` is the LangGraph checkpoint key. It is auto-generated as
`thread-<12-hex-chars>` in `build_and_run()` if not provided, ensuring every
run produces a traceable, unique session. The `incident_id` is similarly
auto-generated as `INC-<8-hex-chars>` if the input alert lacks one.
