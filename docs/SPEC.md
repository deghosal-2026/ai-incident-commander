# SPEC — ai-incident-commander

| Field | Value |
|---|---|
| **Project** | ai-incident-commander — AI incident commander for war rooms, timelines, and postmortems |
| **Document type** | Technical Specification (How) |
| **Status** | Approved ✅ |
| **Created** | 2026-07-12 |
| **Owner** | Debashish Ghosal |
| **PRD reference** | `docs/PRD.md` |
| **Target release** | v0.1.0 |

> This document specifies HOW each requirement in the PRD is implemented. Every FR, threat mitigation, and open question is addressed here. If a requirement is not in this SPEC, it is not being built.

---

## 1. Architecture overview

### 1.1 Component diagram

```
                    ┌──────────────────────────────────────────────────────────┐
                    │              Incident Commander Agent                     │
                    │            (LangGraph StateGraph — foreground CLI)        │
                    │                                                           │
  alert JSON ──────▶│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐  │
  log files ───────▶│  │ receive_alert│───▶│ build_timeline│───▶│ correlate   │  │
  chat export ─────▶│  │             │    │              │    │ _deploys    │  │
  GitHub JSON ─────▶│  └─────────────┘    └──────────────┘    └──────┬──────┘  │
  runbooks ────────▶│                                                │         │
                    │                                                ▼         │
                    │  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐  │
                    │  │ retrieve    │◀───│ draft_update  │◀───│ cadence     │  │
                    │  │ _runbooks   │    │ (LLM)         │    │ _timer      │  │
                    │  └──────┬──────┘    └──────┬───────┘    └─────────────┘  │
                    │         │                  │                             │
                    │         ▼                  ▼                             │
                    │  ┌─────────────┐    ┌──────────────┐                     │
                    │  │ rerank      │    │ interrupt    │                     │
                    │  │ _evidence   │    │ _approval    │                     │
                    │  └──────┬──────┘    └──────┬───────┘                     │
                    │         │                  │                             │
                    │         ▼          ┌───────┴────────┐                    │
                    │  ┌─────────────┐   ▼                 ▼                    │
                    │  │ suggest     │  approve          reject                 │
                    │  │ _remediation│  │                 │                     │
                    │  │ (LLM)       │  ▼                 ▼                     │
                    │  └──────┬──────┘ ┌──────────┐  ┌──────────┐               │
                    │         │        │ produce  │  │ redraft  │               │
                    │         ▼        │ _pasteable│  │ (loop)   │               │
                    │  ┌─────────────┐│ _output  │  └──────────┘               │
                    │  │ dry_run     ││ └──────────┘                            │
                    │  │ _simulate   ││                                         │
                    │  └──────┬──────┘│                                         │
                    │         │       │                                         │
                    │         ▼       │                                         │
                    │  ┌─────────────┐│                                         │
                    │  │ interrupt   ││                                         │
                    │  │ _remediation││                                         │
                    │  │ _review     ││                                         │
                    │  └──────┬──────┘│                                         │
                    │         │       │                                         │
                    │         ▼       │                                         │
                    │  ┌─────────────┐│                                         │
                    │  │ generate    ││                                         │
                    │  │ _postmortem ││                                         │
                    │  │ (LLM, COE)  ││                                         │
                    │  └──────┬──────┘│                                         │
                    │         │       │                                         │
                    │         ▼       │                                         │
                    │  ┌─────────────┐│                                         │
                    │  │ interrupt   ││                                         │
                    │  │ _postmortem ││                                         │
                    │  │ _review     ││                                         │
                    │  └──────┬──────┘│                                         │
                    │         │       │                                         │
                    │         ▼       │                                         │
                    │  ┌─────────────┐│                                         │
                    │  │ cost_report ││                                         │
                    │  │ + save      ││                                         │
                    │  └─────────────┘│                                         │
                    │                  │                                         │
                    │         ▼        ▼                                         │
                    │  ┌──────────────────────────────┐                         │
                    │  │     LLM Router                │                         │
                    │  │  ┌─────────┐  ┌────────────┐ │                         │
                    │  │  │ Local   │  │ Cloud      │ │                         │
                    │  │  │ (OMLX/  │  │ (OpenAI/   │ │                         │
                    │  │  │  Ollama)│  │  Anthropic)│ │                         │
                    │  │  └─────────┘  └────────────┘ │                         │
                    │  └──────────────────────────────┘                         │
                    │                                                           │
                    │  ┌──────────────────────────────┐                         │
                    │  │  CostTracker + LLMObserver    │                         │
                    │  │  (per-node token/cost/latency)│                         │
                    │  └──────────────────────────────┘                         │
                    │                                                           │
                    │  ┌──────────────────────────────┐                         │
                    │  │  Checkpointer (SQLite)        │                         │
                    │  │  (session persistence)         │                         │
                    │  └──────────────────────────────┘                         │
                    │                                                           │
                    └──────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                               Pasteable Output
                               (markdown blocks — user pastes)
```

### 1.2 Module structure

```
incident_commander/
├── __init__.py                  # Public API: run, simulate, __version__
├── cli.py                       # CLI entry point (incident-commander ...)
├── config.py                    # Config (Pydantic) + validation + env loading
├── graph.py                     # LangGraph StateGraph definition + wiring
│
├── models/
│   ├── __init__.py
│   ├── alert.py                 # Alert — severity, service, summary, source, timestamp
│   ├── timeline.py              # TimelineEvent — timestamp, source, type, content, trust
│   ├── incident_state.py        # IncidentState — full state schema
│   ├── war_room.py              # WarRoom — channel info, participants (simulated in v0.1.0)
│   ├── stakeholder_update.py    # StakeholderUpdate — impact, cause, action, next_update
│   ├── remediation.py           # RemediationSuggestion — action, citation, confidence, dry_run
│   ├── postmortem.py            # Postmortem — COE format, sections, AI labels
│   ├── deploy.py                # DeployCorrelation — PR number, title, author, merge_time
│   └── cost.py                  # CostReport — per-node breakdown, total
│
├── nodes/
│   ├── __init__.py
│   ├── receive_alert.py         # Parse alert JSON → state
│   ├── build_timeline.py        # Merge multi-source events → chronological timeline
│   ├── correlate_deploys.py     # Match GitHub PRs within 30-min window
│   ├── retrieve_runbooks.py     # Query knowledge base → runbooks + past incidents
│   ├── rerank_evidence.py       # Rerank retrieved evidence by relevance
│   ├── draft_update.py          # LLM generates consequence-first stakeholder update
│   ├── interrupt_approval.py    # LangGraph interrupt — commander approves/rejects
│   ├── produce_output.py        # Generate pasteable markdown blocks
│   ├── suggest_remediation.py   # LLM pattern-matches past incidents → suggestion
│   ├── dry_run_simulate.py      # LLM simulates expected outcome without executing
│   ├── interrupt_remediation.py # LangGraph interrupt — commander reviews suggestion
│   ├── generate_postmortem.py   # LLM generates COE-format postmortem draft
│   ├── interrupt_postmortem.py  # LangGraph interrupt — commander reviews postmortem
│   └── cost_report.py           # Aggregate cost + save session + emit report
│
├── tools/
│   ├── __init__.py
│   ├── github.py                # GitHub deploy correlation from JSON export or API
│   ├── rag.py                   # Knowledge base query (Qdrant optional, in-memory default)
│   ├── llm.py                   # LLM router — local (OMLX/Ollama) + cloud (OpenAI/Anthropic)
│   ├── cost.py                  # CostTracker — per-call token + cost tracking
│   ├── llm_observer.py          # LLMObserver — per-node prompt/response/tokens/latency logging
│   └── pasteable.py             # PasteableOutput — generates incident notes + comms blocks
│
├── simulation/
│   ├── __init__.py
│   ├── incident_simulator.py    # Generates fake alert, logs, messages, PRs
│   ├── scenarios.py             # Pre-built scenario library (5-8 scenarios)
│   └── demo_runbooks.py         # Pre-indexed demo runbooks for simulation mode
│
└── persistence/
    ├── __init__.py
    └── checkpointer.py          # SQLite checkpointer wrapper + session export
```

### 1.3 Dependency graph

```
                    langchain-core (required)
                    langgraph (required)
                         │
                    pydantic (required)
                         │
               ┌──────────┴──────────┐
               │  incident_commander  │
               │      (core)          │
               └──────────┬──────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
     qdrant-client    rich (CLI)    langchain-openai
     (extra: rag)     (required)    langchain-anthropic
                                   (extras: openai, anthropic)
```

Core install = `langchain-core` + `langgraph` + `pydantic` + `rich` (CLI formatting). RAG (Qdrant) and cloud LLM providers are optional extras.

---

## 2. Core data models

### 2.1 IncidentState (LangGraph state schema)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class IncidentState(BaseModel):
    """Full state schema for the incident commander graph."""

    # Alert
    alert: Optional[Alert] = None
    severity: Literal["SEV1", "SEV2", "SEV3"] = "SEV3"
    service: str = ""
    incident_id: str = ""

    # Timeline
    timeline: list[TimelineEvent] = Field(default_factory=list)

    # Deploy correlation
    deploy_correlations: list[DeployCorrelation] = Field(default_factory=list)

    # Runbooks & past incidents (from RAG)
    retrieved_runbooks: list[dict] = Field(default_factory=list)
    retrieved_incidents: list[dict] = Field(default_factory=list)
    reranked_evidence: list[dict] = Field(default_factory=list)

    # Stakeholder updates
    stakeholder_updates: list[StakeholderUpdate] = Field(default_factory=list)
    current_update_draft: Optional[StakeholderUpdate] = None
    update_approved: bool = False

    # Remediation
    remediation_suggestions: list[RemediationSuggestion] = Field(default_factory=list)
    current_remediation: Optional[RemediationSuggestion] = None
    remediation_approved: bool = False

    # Postmortem
    postmortem: Optional[Postmortem] = None
    postmortem_approved: bool = False

    # Cost
    cost_report: Optional[CostReport] = None

    # Session
    thread_id: str = ""
    mode: Literal["simulate", "run"] = "simulate"
    resolved: bool = False

    # Cadence
    last_update_time: Optional[datetime] = None
    next_update_time: Optional[datetime] = None
```

### 2.2 Alert

```python
class Alert(BaseModel):
    """Parsed alert from JSON input."""
    severity: Literal["SEV1", "SEV2", "SEV3"]
    service: str
    summary: str
    source: str = "manual"  # "pagerduty", "manual", "simulated"
    timestamp: datetime
    incident_id: str = ""
    metadata: dict = Field(default_factory=dict)
```

### 2.3 TimelineEvent

```python
class TimelineEvent(BaseModel):
    """A single event in the incident timeline."""
    timestamp: datetime
    source: Literal["alert", "chat", "log", "github", "manual"]
    event_type: str  # "alert_fired", "error_spike", "pr_merged", "message", etc.
    content: str
    trust_level: Literal["high", "medium", "low"]
    deploy_correlation: bool = False  # True if within 30 min of alert
```

### 2.4 DeployCorrelation

```python
class DeployCorrelation(BaseModel):
    """A GitHub PR/commit correlated with the incident."""
    pr_number: int
    pr_title: str
    author: str
    merge_time: datetime
    files_changed: list[str] = Field(default_factory=list)
    minutes_before_alert: int  # how many minutes before alert fired
    correlation_strength: Literal["strong", "weak"] = "strong"  # strong = <15 min, weak = <30 min
```

### 2.5 StakeholderUpdate

```python
class StakeholderUpdate(BaseModel):
    """A drafted stakeholder update in consequence-first format."""
    update_number: int
    impact: str       # what's broken, who's affected
    root_cause_hypothesis: str  # current best guess
    action: str       # what we're doing about it
    next_update_time: datetime  # when the next update will come
    confidence: float = 1.0  # LLM confidence in the draft
    approved: bool = False
    timestamp: datetime
```

### 2.6 RemediationSuggestion

```python
class RemediationSuggestion(BaseModel):
    """A remediation suggestion with citation and dry-run."""
    action: str  # "Rollback PR #4892"
    citation: str  # "Source: incident INC-2025-088"
    confidence: float  # 0.0–1.0
    dry_run_outcome: str  # "Expected: payment success >99% within 2 min of rollback"
    similar_incidents: list[str] = Field(default_factory=list)  # incident IDs
    approved: bool = False
```

### 2.7 Postmortem (COE format)

```python
class PostmortemSection(BaseModel):
    """A single section of the postmortem."""
    title: str
    content: str
    ai_generated: bool = True  # True = LLM wrote this, False = human wrote/edited

class Postmortem(BaseModel):
    """Amazon COE (Correction of Errors) format postmortem."""
    incident_id: str
    incident_date: datetime
    severity: str
    service: str

    # COE sections
    summary: PostmortemSection
    timeline: PostmortemSection  # from session state
    root_cause_analysis: PostmortemSection  # LLM with citations
    systemic_contributing_factors: PostmortemSection  # blameless framing
    action_items: list[ActionItem]  # with suggested owners

    # Metadata
    resolved_at: Optional[datetime] = None
    mttr_minutes: Optional[int] = None
    approved: bool = False

class ActionItem(BaseModel):
    """A corrective action from the postmortem."""
    description: str
    suggested_owner: str
    priority: Literal["P0", "P1", "P2"] = "P1"
    ai_generated: bool = True
```

### 2.8 CostReport

```python
class NodeCost(BaseModel):
    """Cost breakdown for a single agent node."""
    node_name: str
    llm_model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    latency_ms: int

class CostReport(BaseModel):
    """Aggregate cost report for an incident session."""
    session_id: str
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_estimated_cost_usd: float
    per_node: list[NodeCost]
    models_used: list[str]
```

### 2.9 Config

```python
class LLMConfig(BaseModel):
    """LLM routing configuration."""
    analysis_model: str = "ollama/qwen2.5-coder:7b"  # local default
    analysis_base_url: str = "http://localhost:11434/v1"
    comms_model: Optional[str] = None  # None = use analysis model for comms too
    comms_base_url: Optional[str] = None
    postmortem_model: Optional[str] = None  # None = use analysis model
    postmortem_base_url: Optional[str] = None

    # Cost estimates (per 1M tokens)
    model_pricing: dict[str, dict[str, float]] = Field(default_factory=lambda: {
        "ollama/qwen2.5-coder:7b": {"input": 0.0, "output": 0.0},  # local = free
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    })

class Config(BaseModel):
    """Top-level configuration."""
    # Mode
    mode: Literal["simulate", "run"] = "simulate"

    # LLM
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # Cadence (minutes between stakeholder updates)
    cadence: dict[str, int] = Field(default_factory=lambda: {
        "SEV1": 5,
        "SEV2": 15,
        "SEV3": 30,
    })

    # Safety
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    deploy_correlation_window_minutes: int = 30

    # RAG (optional)
    qdrant_url: Optional[str] = None
    qdrant_collection: str = "runbooks"

    # GitHub (optional API mode)
    github_token: Optional[str] = None  # None = JSON export mode only

    # Persistence
    session_dir: str = "~/.incident-commander/sessions"
    log_dir: str = "~/.incident-commander/logs"

    # Output
    output_format: Literal["markdown", "json"] = "markdown"
```

---

## 3. LangGraph state graph (FR-2, FR-3, FR-4, FR-5, FR-6, FR-9, FR-10)

### 3.1 Graph definition

```python
# incident_commander/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

def build_graph(config: Config) -> StateGraph:
    graph = StateGraph(IncidentState)

    # Nodes
    graph.add_node("receive_alert", receive_alert_node)
    graph.add_node("build_timeline", build_timeline_node)
    graph.add_node("correlate_deploys", correlate_deploys_node)
    graph.add_node("retrieve_runbooks", retrieve_runbooks_node)
    graph.add_node("rerank_evidence", rerank_evidence_node)
    graph.add_node("draft_update", draft_update_node)
    graph.add_node("interrupt_approval", interrupt_approval_node)
    graph.add_node("produce_output", produce_output_node)
    graph.add_node("suggest_remediation", suggest_remediation_node)
    graph.add_node("dry_run_simulate", dry_run_simulate_node)
    graph.add_node("interrupt_remediation", interrupt_remediation_node)
    graph.add_node("generate_postmortem", generate_postmortem_node)
    graph.add_node("interrupt_postmortem", interrupt_postmortem_node)
    graph.add_node("cost_report", cost_report_node)

    # Edges — linear flow with cycles
    graph.set_entry_point("receive_alert")
    graph.add_edge("receive_alert", "build_timeline")
    graph.add_edge("build_timeline", "correlate_deploys")
    graph.add_edge("correlate_deploys", "retrieve_runbooks")
    graph.add_edge("retrieve_runbooks", "rerank_evidence")
    graph.add_edge("rerank_evidence", "draft_update")

    # Stakeholder update cycle
    graph.add_edge("draft_update", "interrupt_approval")
    graph.add_conditional_edges(
        "interrupt_approval",
        lambda state: "produce_output" if state.update_approved else "draft_update",
    )
    graph.add_edge("produce_output", "draft_update")  # cycle back for next update

    # Commander can resolve incident at any interrupt → go to remediation
    graph.add_conditional_edges(
        "interrupt_approval",
        lambda state: "suggest_remediation" if state.resolved else None,
    )

    # Remediation flow
    graph.add_edge("suggest_remediation", "dry_run_simulate")
    graph.add_edge("dry_run_simulate", "interrupt_remediation")
    graph.add_conditional_edges(
        "interrupt_remediation",
        lambda state: "generate_postmortem" if state.remediation_approved
        else "suggest_remediation",  # ask for alternatives
    )

    # Postmortem flow
    graph.add_edge("generate_postmortem", "interrupt_postmortem")
    graph.add_conditional_edges(
        "interrupt_postmortem",
        lambda state: "cost_report" if state.postmortem_approved
        else "generate_postmortem",  # regenerate
    )

    graph.add_edge("cost_report", END)

    return graph
```

### 3.2 Visual graph

```
receive_alert
    │
    ▼
build_timeline ──▶ correlate_deploys ──▶ retrieve_runbooks ──▶ rerank_evidence
                                                                    │
                                                                    ▼
    ┌─────────────────────────────────────────────────── draft_update
    │                                                        │
    │                                                        ▼
    │                                               interrupt_approval
    │                                                    │
    │                                          ┌────────┴────────┐
    │                                          │                 │
    │                                       approve            reject
    │                                          │                 │
    │                                          ▼                 ▼
    │                                    produce_output      draft_update
    │                                          │           (redraft loop)
    │                                          ▼
    │                                    draft_update
    │                                   (next cycle)
    │
    │  (commander resolves incident at any interrupt)
    ▼
suggest_remediation ──▶ dry_run_simulate ──▶ interrupt_remediation
                                                │
                                       ┌────────┴────────┐
                                       │                 │
                                    approve            reject
                                       │                 │
                                       ▼                 ▼
                                generate_postmortem  suggest_remediation
                                       │           (alternatives loop)
                                       ▼
                                interrupt_postmortem
                                       │
                              ┌────────┴────────┐
                              │                 │
                           approve            reject
                              │                 │
                              ▼                 ▼
                         cost_report     generate_postmortem
                              │           (regenerate loop)
                              ▼
                             END
```

### 3.3 Interrupt points

| Interrupt | Node | What happens | Commander options |
|---|---|---|---|
| **INT-1** | `interrupt_approval` | Stakeholder update draft displayed | `[a]` approve → produce pasteable output; `[e]` edit → modify then approve; `[r]` reject → redraft; `[x]` resolve → incident resolved, go to remediation |
| **INT-2** | `interrupt_remediation` | Remediation suggestion + dry-run outcome displayed | `[a]` accept → note for postmortem, go to PM; `[r]` reject → ask for alternatives; `[s]` skip → go to PM without remediation |
| **INT-3** | `interrupt_postmortem` | COE postmortem draft displayed with AI sections labeled | `[a]` approve → save as markdown; `[e]` edit sections → modify then save; `[r]` regenerate → try different LLM or same LLM with adjusted prompt |

### 3.4 Foreground CLI interrupt implementation

```python
# incident_commander/nodes/interrupt_approval.py
from langgraph.types import interrupt
from rich.console import Console
from rich.panel import Panel

console = Console()

def interrupt_approval_node(state: IncidentState) -> IncidentState:
    """Display stakeholder update draft and wait for commander approval."""
    draft = state.current_update_draft

    # Display the draft
    console.print(Panel(
        f"[bold]Impact:[/bold] {draft.impact}\n"
        f"[bold]Root Cause:[/bold] {draft.root_cause_hypothesis}\n"
        f"[bold]Action:[/bold] {draft.action}\n"
        f"[bold]Next Update:[/bold] {draft.next_update_time.strftime('%H:%M')} "
        f"({state.severity} cadence: {state.cadence_minutes} min)",
        title=f"── Stakeholder Update Draft #{draft.update_number} ──",
    ))

    if draft.confidence < state.confidence_threshold:
        console.print("[yellow]⚠ Low confidence draft — consider editing[/yellow]")

    # LangGraph interrupt — blocks here in foreground CLI
    choice = interrupt({
        "prompt": "[a] Approve  [e] Edit  [r] Reject (redraft)  [x] Resolve incident",
        "draft": draft.model_dump(),
    })

    match choice:
        case "a":
            state.update_approved = True
            state.stakeholder_updates.append(draft)
        case "e":
            edited = cli_edit_update(draft)
            state.current_update_draft = edited
            state.update_approved = True
            state.stakeholder_updates.append(edited)
        case "r":
            state.update_approved = False  # cycle back to draft_update
        case "x":
            state.resolved = True
            state.update_approved = True
            state.stakeholder_updates.append(draft)

    return state
```

### 3.5 Cadence timer

```python
# incident_commander/nodes/draft_update.py
import asyncio
from datetime import datetime, timedelta

def draft_update_node(state: IncidentState) -> IncidentState:
    """Draft a stakeholder update on the severity-driven cadence."""

    # Check if it's time for the next update
    cadence_minutes = state.config.cadence[state.severity]
    now = datetime.now()

    if state.last_update_time:
        elapsed = (now - state.last_update_time).total_seconds() / 60
        if elapsed < cadence_minutes:
            # Not time yet — wait
            wait_seconds = (cadence_minutes - elapsed) * 60
            # In simulation mode, wait is simulated (accelerated)
            if state.mode == "simulate":
                wait_seconds = min(wait_seconds, 2)  # 2 sec per simulated cycle
            asyncio.run(asyncio.sleep(wait_seconds))

    # Build LLM prompt
    prompt = build_update_prompt(state)

    # Call LLM (routed based on config)
    response, llm_info = llm_router.generate(
        prompt=prompt,
        task="stakeholder_update",
        model=state.config.llm.comms_model or state.config.llm.analysis_model,
    )

    # Parse into StakeholderUpdate
    update = parse_update_response(response, state)

    # Track cost
    cost_tracker.record(
        node_name="draft_update",
        model=llm_info.model,
        input_tokens=llm_info.input_tokens,
        output_tokens=llm_info.output_tokens,
        latency_ms=llm_info.latency_ms,
    )

    state.current_update_draft = update
    state.last_update_time = now
    state.next_update_time = now + timedelta(minutes=cadence_minutes)

    return state
```

---

## 4. Incident simulation (FR-1)

### 4.1 IncidentSimulator

```python
# incident_commander/simulation/incident_simulator.py
import random
from datetime import datetime, timedelta

class IncidentSimulator:
    """Generates fake alerts, logs, messages, and PRs for simulation mode."""

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def simulate(
        self,
        service: str,
        severity: str,
        num_logs: int = 15,
        num_messages: int = 8,
        num_prs: int = 3,
    ) -> SimulationData:
        """Generate a complete simulated incident dataset."""
        base_time = datetime.now()

        alert = self._generate_alert(service, severity, base_time)
        logs = self._generate_logs(service, base_time, num_logs)
        messages = self._generate_messages(service, base_time, num_messages)
        prs = self._generate_prs(service, base_time, num_prs)
        runbooks = self._load_demo_runbooks(service)
        past_incidents = self._generate_past_incidents(service, num_incidents=5)

        return SimulationData(
            alert=alert,
            logs=logs,
            messages=messages,
            prs=prs,
            runbooks=runbooks,
            past_incidents=past_incidents,
        )
```

### 4.2 Pre-built scenario library (FR-1.6)

```python
# incident_commander/simulation/scenarios.py

SCENARIOS: dict[str, ScenarioConfig] = {
    "db-connection-pool": ScenarioConfig(
        name="db-connection-pool",
        description="DB connection pool exhaustion causing payment failures",
        service="payment-service",
        severity="SEV1",
        num_logs=20,
        num_messages=12,
        num_prs=2,
        root_cause="db_connection_pool_exhaustion",
        deploy_correlated=True,
        expected_runbook_matches=["rb-001"],
    ),
    "bad-deploy": ScenarioConfig(
        name="bad-deploy",
        description="Misconfigured route in API gateway from bad deploy",
        service="api-gateway",
        severity="SEV2",
        num_logs=15,
        num_messages=8,
        num_prs=1,
        root_cause="misconfigured_route",
        deploy_correlated=True,
        expected_runbook_matches=["rb-002"],
    ),
    "memory-leak": ScenarioConfig(
        name="memory-leak",
        description="Gradual memory growth causing OOM kills in auth service",
        service="auth-service",
        severity="SEV2",
        num_logs=10,
        num_messages=5,
        num_prs=1,
        root_cause="memory_leak",
        deploy_correlated=False,
        expected_runbook_matches=["rb-006"],
    ),
    "cert-expiry": ScenarioConfig(
        name="cert-expiry",
        description="TLS certificate expired on API gateway",
        service="api-gateway",
        severity="SEV1",
        num_logs=12,
        num_messages=8,
        num_prs=0,
        root_cause="cert_expired",
        deploy_correlated=False,
        expected_runbook_matches=["rb-003"],
    ),
    "dependency-outage": ScenarioConfig(
        name="dependency-outage",
        description="Third-party payment API is down",
        service="payment-service",
        severity="SEV1",
        num_logs=18,
        num_messages=10,
        num_prs=0,
        root_cause="third_party_down",
        deploy_correlated=False,
        expected_runbook_matches=[],
    ),
    "config-drift": ScenarioConfig(
        name="config-drift",
        description="Stale configuration in web frontend",
        service="web-frontend",
        severity="SEV3",
        num_logs=6,
        num_messages=3,
        num_prs=1,
        root_cause="stale_config",
        deploy_correlated=False,
        expected_runbook_matches=[],
    ),
    "cache-invalidation": ScenarioConfig(
        name="cache-invalidation",
        description="Stale cache returns incorrect product data",
        service="product-catalog",
        severity="SEV2",
        num_logs=10,
        num_messages=6,
        num_prs=0,
        root_cause="stale_cache",
        deploy_correlated=False,
        expected_runbook_matches=["rb-004"],
    ),
    "rate-limit-hit": ScenarioConfig(
        name="rate-limit-hit",
        description="Upstream rate limit exceeded causing degraded search",
        service="search-service",
        severity="SEV3",
        num_logs=8,
        num_messages=4,
        num_prs=0,
        root_cause="rate_limit_exceeded",
        deploy_correlated=False,
        expected_runbook_matches=["rb-005"],
    ),
}
```

### 4.3 Demo runbooks (FR-7.5)

```python
# incident_commander/simulation/demo_runbooks.py
"""Pre-indexed demo runbooks for simulation mode. In-memory, no Qdrant needed."""

DEMO_RUNBOOKS: list[dict] = [
    {
        "id": "rb-001",
        "service": "payment-service",
        "title": "DB Connection Pool Exhaustion",
        "path": "runbooks/payment-service/db-connection-pool.md",
        "section": "Triage",
        "content": "1. Check active connections: `SELECT count(*) FROM pg_stat_activity`...",
        "keywords": ["db", "connection", "pool", "exhaustion", "timeout"],
    },
    # ... 10+ more demo runbooks covering common incident types
]

DEMO_PAST_INCIDENTS: list[dict] = [
    {
        "id": "INC-2025-088",
        "service": "payment-service",
        "severity": "SEV1",
        "date": "2025-11-15",
        "summary": "DB connection pool exhaustion. Resolved by rollback.",
        "resolution": "Rolled back PR #4521. Connection pool size increased.",
        "keywords": ["db", "connection", "pool", "rollback"],
    },
    # ... 10+ more past incidents
]
```

---

## 5. Timeline construction (FR-2)

### 5.1 build_timeline_node

```python
# incident_commander/nodes/build_timeline.py

TRUST_MAP: dict[str, Literal["high", "medium", "low"]] = {
    "alert": "high",      # PagerDuty alerts
    "chat": "high",       # Slack messages
    "github": "high",     # GitHub PRs/commits
    "log": "medium",      # Log entries
    "manual": "low",      # Human-entered
}

def build_timeline_node(state: IncidentState) -> IncidentState:
    """Merge events from all sources into a chronological timeline."""
    events: list[TimelineEvent] = []

    # Alert event
    if state.alert:
        events.append(TimelineEvent(
            timestamp=state.alert.timestamp,
            source="alert",
            event_type="alert_fired",
            content=state.alert.summary,
            trust_level="high",
        ))

    # Log events (from provided log files or simulation)
    for log_entry in state.input_logs:
        events.append(TimelineEvent(
            timestamp=log_entry.timestamp,
            source="log",
            event_type=log_entry.level,
            content=log_entry.message,
            trust_level="medium",
        ))

    # Chat events (from provided export or simulation)
    for msg in state.input_messages:
        events.append(TimelineEvent(
            timestamp=msg.timestamp,
            source="chat",
            event_type="message",
            content=f"{msg.author}: {msg.text}",
            trust_level="high",
        ))

    # Sort chronologically
    events.sort(key=lambda e: e.timestamp)

    state.timeline = events
    return state
```

### 5.2 Timeline display (FR-2.3, FR-2.4)

```python
# incident_commander/nodes/build_timeline.py

def format_timeline(timeline: list[TimelineEvent]) -> str:
    """Human-readable timeline for CLI display."""
    lines = []
    for event in timeline:
        trust_marker = {
            "high": "",
            "medium": " (trust: medium)",
            "low": " (trust: LOW — human-entered)",
        }[event.trust_level]

        deploy_marker = " [DEPLOY CORRELATION]" if event.deploy_correlation else ""

        lines.append(
            f"{event.timestamp.strftime('%H:%M:%S')} {event.content}"
            f"{trust_marker}{deploy_marker}"
        )
    return "\n".join(lines)
```

---

## 6. GitHub deploy correlation (FR-3)

### 6.1 correlate_deploys_node

```python
# incident_commander/nodes/correlate_deploys.py
from datetime import timedelta

def correlate_deploys_node(state: IncidentState) -> IncidentState:
    """Correlate recent GitHub PRs/commits with the alert timestamp."""
    if not state.alert:
        return state

    alert_time = state.alert.timestamp
    window = timedelta(minutes=state.config.deploy_correlation_window_minutes)
    correlations = []

    for pr in state.input_prs:
        time_diff = (alert_time - pr.merge_time).total_seconds() / 60

        # Only PRs merged BEFORE the alert, within the window
        if 0 < time_diff <= state.config.deploy_correlation_window_minutes:
            strength = "strong" if time_diff <= 15 else "weak"
            correlations.append(DeployCorrelation(
                pr_number=pr.number,
                pr_title=pr.title,
                author=pr.author,
                merge_time=pr.merge_time,
                files_changed=pr.files_changed,
                minutes_before_alert=int(time_diff),
                correlation_strength=strength,
            ))

            # Mark timeline events for this PR
            for event in state.timeline:
                if event.source == "github" and pr.merge_time == event.timestamp:
                    event.deploy_correlation = True

    state.deploy_correlations = correlations
    return state
```

### 6.2 GitHub JSON export format

```json
[
  {
    "number": 4892,
    "title": "Update payment_processor.py — increase pool size",
    "author": "jdoe",
    "merge_time": "2026-07-12T13:48:00Z",
    "files_changed": ["src/payment_processor.py", "config/pool.yaml"]
  }
]
```

### 6.3 GitHub API mode (FR-3.5, optional)

```python
# incident_commander/tools/github.py
import httpx

class GitHubClient:
    """Optional GitHub API client. Works without token (JSON export mode)."""

    def __init__(self, token: str | None = None, repo: str | None = None):
        self._token = token
        self._repo = repo

    def get_recent_prs(self, hours: int = 2) -> list[dict]:
        """Fetch recent merged PRs. Requires token + repo."""
        if not self._token or not self._repo:
            raise ValueError("GitHub API mode requires token and repo")

        response = httpx.get(
            f"https://api.github.com/repos/{self._repo}/pulls",
            params={"state": "closed", "sort": "updated", "direction": "desc"},
            headers={"Authorization": f"token {self._token}"},
        )
        # Filter to merged PRs within the time window
        return [pr for pr in response.json() if self._is_recent_merge(pr, hours)]
```

---

## 7. Stakeholder communication (FR-4)

### 7.1 draft_update_node

```python
# incident_commander/nodes/draft_update.py

UPDATE_PROMPT = """\
You are an AI incident commander assistant. Draft a stakeholder update \
in consequence-first format. Be clinical, precise, and factual. No emojis.

## Incident context
- Service: {service}
- Severity: {severity}
- Alert summary: {alert_summary}
- Current timeline: {timeline_summary}
- Deploy correlations: {deploy_summary}
- Evidence from runbooks: {evidence_summary}

## Output format (exactly)
Impact: <what's broken, who's affected, quantify if possible>
Root cause: <current best hypothesis based on evidence>
Action: <what we're doing about it right now>
Next update: <time, {cadence} minutes from now>

## Rules
- If confidence in root cause is low, say "Under investigation"
- Quantify impact (e.g., "2% of payment attempts failing")
- Never speculate beyond what the evidence supports
- Clinical tone — no "we're working hard" or "unfortunately"
"""
```

### 7.2 produce_output_node (FR-4.4)

```python
# incident_commander/nodes/produce_output.py

def produce_output_node(state: IncidentState) -> IncidentState:
    """Generate pasteable markdown blocks after approval."""
    update = state.current_update_draft

    # Incident notes block (for PagerDuty, ticketing)
    incident_notes = format_incident_notes(state, update)

    # Stakeholder comms block (for Slack, email)
    comms_block = format_comms_block(state, update)

    # Display both blocks
    console.print(Panel(incident_notes, title="── Incident Notes Block (paste into PagerDuty/ticket) ──"))
    console.print(Panel(comms_block, title="── Stakeholder Comms Block (paste into Slack/email) ──"))

    # Save to state for later export
    state.pasteable_outputs.append({
        "update_number": update.update_number,
        "incident_notes": incident_notes,
        "comms_block": comms_block,
    })

    return state


def format_comms_block(state: IncidentState, update: StakeholderUpdate) -> str:
    return f"""## {state.severity} — {state.service} Incident

**Impact:** {update.impact}
**Root cause:** {update.root_cause_hypothesis}
**Action:** {update.action}
**Next update:** {update.next_update_time.strftime('%H:%M UTC')} ({state.cadence_minutes} min)
"""
```

---

## 8. Remediation suggestion (FR-5)

### 8.1 suggest_remediation_node

```python
# incident_commander/nodes/suggest_remediation.py

REMEDIATION_PROMPT = """\
You are an AI incident commander assistant. Based on the current incident \
and historical data, suggest a remediation action.

## Current incident
- Service: {service}
- Severity: {severity}
- Symptoms: {symptoms}
- Timeline: {timeline_summary}
- Deploy correlations: {deploy_summary}

## Similar past incidents
{past_incidents}

## Relevant runbooks
{runbooks}

## Output format
Action: <specific action to take, e.g., "Rollback PR #4892">
Citation: <source, e.g., "Source: incident INC-2025-088">
Confidence: <0.0 to 1.0>
Similar incidents: <list of incident IDs>
Reasoning: <1-2 sentences explaining why>

## Rules
- Only suggest actions that a human can execute manually
- NEVER suggest auto-execution — the commander executes, not the tool
- Cite the source of every suggestion
- If no relevant past incidents, say "No historical data available"
- If confidence < {threshold}, say "No high-confidence suggestion available"
"""
```

### 8.2 dry_run_simulate_node (FR-5.7)

```python
# incident_commander/nodes/dry_run_simulate.py

DRY_RUN_PROMPT = """\
You are an AI incident commander assistant. Simulate the expected outcome \
of the suggested remediation WITHOUT executing it.

## Suggested action
{action}

## Current state
- Service: {service}
- Error rate: {error_rate}
- Current timeline: {timeline_summary}

## Simulation
Based on similar past incidents and the suggested action, describe what \
would likely happen if this action is executed. Be specific and realistic.

## Output format
Expected outcome: <what should happen after the action>
Time to recovery: <estimated time>
Risk: <any risks of the action>
Confidence: <0.0 to 1.0>
"""
```

### 8.3 Evidence reranking (FR-5.8, FR-7.6)

```python
# incident_commander/nodes/rerank_evidence.py

def rerank_evidence_node(state: IncidentState) -> IncidentState:
    """Rerank retrieved runbooks and past incidents by relevance to current symptoms."""
    query = f"{state.service} {state.alert.summary}"

    # Combine runbooks + past incidents
    all_evidence = state.retrieved_runbooks + state.retrieved_incidents

    # Score by keyword overlap + recency + source trust
    scored = []
    for item in all_evidence:
        score = compute_relevance_score(query, item)
        scored.append((score, item))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Keep top N
    state.reranked_evidence = [item for _, item in scored[:10]]
    return state


def compute_relevance_score(query: str, item: dict) -> float:
    """Score relevance: keyword overlap (0.5) + recency (0.3) + severity match (0.2)."""
    keyword_score = compute_keyword_overlap(query, item.get("keywords", []))
    recency_score = compute_recency(item.get("date"))
    severity_score = 1.0 if item.get("severity") == query_severity else 0.5
    return 0.5 * keyword_score + 0.3 * recency_score + 0.2 * severity_score
```

---

## 9. Postmortem generation (FR-6)

### 9.0 COE format research — parsing public postmortems

Before implementing the postmortem generator, we parse publicly available postmortem documents from Amazon (COE) and Google (SRE Book postmortem templates) to derive the correct template for each severity level. This ensures our COE prompt and output format match what real SRE teams actually write — not what we assume they write.

#### 9.0.1 Sources to parse

| Source | URL | Format | Why |
|---|---|---|---|
| AWS COE template | AWS public COE examples (Google search: "AWS correction of errors template") | Amazon COE | The native Amazon format we're targeting |
| Google SRE Book — Postmortem chapter | `https://sre.google/sre-book/postmortem-culture/` | Google postmortem template | Industry-standard blameless PM format; overlaps with COE |
| Google SRE Book — Postmortem templates | `https://github.com/google/sample-postmortems` (if available) or SRE Book appendix | Real postmortem examples | Actual postmortems with content, not just templates |
| Public AWS postmortems | AWS engineering blog posts tagged "postmortem" or "COE" | Real Amazon COE documents | See what real SEV1 COEs contain |
| Public incident reports | GitHub postmortem repo: `github.com/danluu/post-mortems` | Curated public postmortems from many companies | Diverse formats and severity levels |
| GitHub's own postmortems | GitHub engineering blog postmortems (2018 outage, etc.) | Real-world SEV1 postmortems | Well-known public SEV1 postmortem with timeline + RCA |
| Cloudflare postmortems | Cloudflare blog postmortem posts | Real-world SEV1 postmortems | Public, detailed, includes timelines |
| GitLab postmortems | GitLab public postmortems (e.g., 2017 data loss, 2023 outage) | Real-world SEV1 postmortems | Very detailed, include timeline, RCA, action items |

#### 9.0.2 Parsing methodology

```python
# incident_commander/research/coe_parser.py
"""
Pre-implementation research script. Not shipped with the package.
Run once during development to derive the COE template.

Usage: python scripts/parse_public_postmortems.py --output docs/coe-analysis.md
"""

import httpx
import re
from pathlib import Path
from dataclasses import dataclass

@dataclass
class PostmortemAnalysis:
    """Parsed structure from a single public postmortem."""
    source: str           # "Amazon COE", "Google SRE", "Cloudflare", etc.
    title: str
    severity: str         # "SEV1", "SEV2", "unknown"
    sections_found: list[str]   # section headings detected
    has_timeline: bool
    has_root_cause: bool
    has_action_items: bool
    has_blameless_framing: bool  # no individual names as causes
    has_systemic_factors: bool
    has_impact_assessment: bool
    has_metrics: bool           # MTTR, error rates, etc.
    has_stakeholder_comms: bool
    word_count: int
    action_item_count: int
    timeline_event_count: int

# Step 1: Fetch public postmortems
SOURCES = [
    # Google SRE Book postmortem chapter (HTML)
    "https://sre.google/sre-book/postmortem-culture/",
    # Dan Luu's curated postmortem list (links to external postmortems)
    "https://github.com/danluu/post-mortems",
    # Cloudflare outage posts (specific known postmortems)
    # GitLab public postmortems
    # GitHub engineering blog postmortems
    # AWS public COE examples
]

def fetch_and_analyze(url: str) -> PostmortemAnalysis:
    """Fetch a public postmortem and analyze its structure."""
    response = httpx.get(url, follow_redirects=True)
    text = response.text

    # Detect section headings (markdown ## or HTML <h2>)
    sections = re.findall(r'(?:##|<h2[^>]*>)\s*(.+?)(?:</h2>|$)', text, re.MULTILINE)

    # Detect key structural elements
    has_timeline = any("timeline" in s.lower() for s in sections)
    has_root_cause = any("root cause" in s.lower() or "rca" in s.lower() for s in sections)
    has_action_items = any("action" in s.lower() or "corrective" in s.lower() for s in sections)
    has_systemic = any("systemic" in s.lower() or "contributing" in s.lower() for s in sections)
    has_impact = any("impact" in s.lower() for s in sections)
    has_metrics = any("mttr" in s.lower() or "metric" in s.lower() for s in sections)

    # Check blameless: no "X's fault" or "X should have" patterns
    blameless_violations = re.findall(r'(?:should have|fault of|caused by \w+\'s)', text, re.IGNORECASE)
    has_blameless = len(blameless_violations) == 0

    return PostmortemAnalysis(
        source=url,
        title=extract_title(text),
        severity=detect_severity(text),
        sections_found=sections,
        has_timeline=has_timeline,
        has_root_cause=has_root_cause,
        has_action_items=has_action_items,
        has_blameless_framing=has_blameless,
        has_systemic_factors=has_systemic,
        has_impact_assessment=has_impact,
        has_metrics=has_metrics,
        has_stakeholder_comms=any("stakeholder" in s.lower() or "communication" in s.lower() for s in sections),
        word_count=len(text.split()),
        action_item_count=len(re.findall(r'(?:^|\n)\s*[-*]\s*\[', text)),
        timeline_event_count=len(re.findall(r'\d{1,2}:\d{2}', text)),
    )

def generate_analysis_report() -> str:
    """Generate docs/coe-analysis.md with findings from all parsed postmortems."""
    results = [fetch_and_analyze(url) for url in SOURCES]

    # Aggregate: which sections appear in >70% of postmortems?
    all_sections = [s for r in results for s in r.sections_found]
    section_freq = Counter(all_sections)
    common_sections = [s for s, count in section_freq.items()
                       if count / len(results) > 0.7]

    # Per-severity analysis
    sev1_results = [r for r in results if r.severity == "SEV1"]

    return format_report(results, common_sections, sev1_results)
```

#### 9.0.3 Analysis output

The script produces `docs/coe-analysis.md` with:

1. **Per-postmortem table** — each public postmortem analyzed: source, severity, sections found, word count, action item count, timeline event count, blameless compliance
2. **Aggregate section frequency** — which sections appear in >70% of postmortems (these become mandatory in our COE template)
3. **SEV1-specific analysis** — what sections are present in SEV1 postmortems specifically (may include sections not in SEV2/SEV3 like executive summary, customer communication log, regulatory impact)
4. **Blameless framing analysis** — which postmortems violate blameless principles and how
5. **Timeline format analysis** — how real postmortems format timelines (bullet list vs table, level of detail, timestamp format)
6. **Action item patterns** — how action items are structured (owner assignment, priority, tracking, due dates)

#### 9.0.4 Template derivation

Based on the analysis, we derive:

| What | How | Where it feeds |
|---|---|---|
| **Mandatory COE sections** | Sections present in >70% of parsed postmortems | `POSTMORTEM_PROMPT` (§9.1) |
| **SEV1-specific sections** | Sections only in SEV1 postmortems (e.g., executive summary, customer comms log) | Severity-conditional in prompt |
| **Timeline format** | Match the most common format from real postmortems | `format_timeline_for_pm()` (§9.2) |
| **Action item format** | Match real postmortem action item structure | `parse_action_items()` (§9.2) |
| **Blameless rules** | Explicit list of anti-patterns found in non-blameless postmortems | `POSTMORTEM_PROMPT` rules section |
| **Section ordering** | Order sections as they appear in real postmortems | `Postmortem` model field order (§2.7) |

#### 9.0.5 SEV1 vs SEV2 vs SEV3 template differences

The analysis determines what differs by severity:

| Element | SEV1 | SEV2 | SEV3 |
|---|---|---|---|
| Executive summary | Required (2-3 paragraphs) | Required (1 paragraph) | Optional |
| Customer impact statement | Required (quantified) | Required | Optional |
| Stakeholder communication log | Required (list of comms sent) | Optional | Not included |
| Timeline detail | Minute-by-minute for first 30 min | Key events only | Key events only |
| Root cause analysis depth | Deep (multiple contributing factors) | Moderate | Brief |
| Systemic contributing factors | Required (3+ factors) | Required (1+ factors) | Optional |
| Action items | Required (P0 + P1) | Required (P1 + P2) | Optional |
| Regulatory/compliance impact | Required if applicable | Not required | Not required |
| MTTR | Required | Required | Optional |

```python
# Severity-conditional prompt in generate_postmortem_node
def build_postmortem_prompt(state: IncidentState) -> str:
    """Build COE prompt with severity-conditional sections."""
    severity_sections = {
        "SEV1": """
### Executive Summary
<2-3 paragraph executive summary — what happened, customer impact, MTTR>

### Customer Impact
<quantified: X% of customers affected, Y hours of degradation, Z revenue impact>

### Stakeholder Communication Log
<list of all stakeholder updates sent during the incident, with timestamps>

### Regulatory/Compliance Impact
<if applicable: any regulatory implications, data exposure, compliance violations>
""",
        "SEV2": """
### Summary
<1 paragraph summary of what happened>

### Customer Impact
<quantified impact>
""",
        "SEV3": """
### Summary
<brief summary of what happened>
""",
    }

    # Common sections (derived from COE analysis)
    common_sections = """
### Timeline
<chronological list — from session state, not LLM-generated>

### Root Cause Analysis
<technical root cause with citations to timeline events>

### Systemic Contributing Factors
<what systemic issues contributed — NOT individual mistakes>

### Action Items
- [ ] <action> — Owner: <team/role> — Priority: P0/P1/P2
"""

    return f"""\
You are an AI incident commander assistant. Generate a postmortem draft \
in Amazon COE (Correction of Errors) format. This is BLAMELESS.

{severity_sections[state.severity]}
{common_sections}

## Blameless rules (derived from analyzing {N} public postmortems)
- Never name individuals as causes — name systems, processes, tooling
- Use passive voice for errors: "the connection pool was exhausted", not "JDOE exhausted the pool"
- Focus on what failed in the system, not who failed in their job
- Every action item targets a systemic improvement, not individual retraining
- Cite timeline events by timestamp: "(see 14:07 in timeline)"
"""
```

#### 9.0.6 Implementation order

1. **Run the COE parser script** — fetch and analyze 10-15 public postmortems
2. **Review `docs/coe-analysis.md`** — verify findings match expectations
3. **Derive the COE template** — finalize mandatory sections, severity-conditional sections, blameless rules
4. **Implement `generate_postmortem_node`** (§9.1) using the derived template
5. **Validate** — run the postmortem generator on simulated SEV1 and compare output structure against real public postmortems

### 9.1 generate_postmortem_node

```python
# incident_commander/nodes/generate_postmortem.py

POSTMORTEM_PROMPT = """\
You are an AI incident commander assistant. Generate a postmortem draft \
in Amazon COE (Correction of Errors) format. This is BLAMELESS — focus \
on what failed, not who failed. Focus on systemic contributing factors.

## Incident data
- Incident ID: {incident_id}
- Service: {service}
- Severity: {severity}
- Start time: {start_time}
- Resolved at: {resolved_at}
- MTTR: {mttr} minutes

## Timeline
{timeline}

## Stakeholder updates
{stakeholder_updates}

## Remediation applied
{remediation}

## Deploy correlations
{deploy_correlations}

## Output format (Amazon COE)
### Summary
<2-3 paragraph executive summary of what happened>

### Timeline
<chronological list of key events — from session state, not LLM-generated>

### Root Cause Analysis
<analysis of the technical root cause, with citations to timeline events>

### Systemic Contributing Factors
<what systemic issues contributed — NOT individual mistakes>
<e.g., "No integration test for connection pool under load", not "JDOE didn't test">

### Action Items
- [ ] <action> — Owner: <suggested team/role> — Priority: P0/P1/P2

## Rules
- BLAMELESS: never name individuals as causes. Name systems, processes, tooling.
- Cite timeline events by timestamp: "(see 14:07 in timeline)"
- Every action item must have a suggested owner (team/role, not individual)
- Label AI-generated sections clearly
"""
```

### 9.2 COE format output

```python
# incident_commander/nodes/generate_postmortem.py

def parse_postmortem(response: str, state: IncidentState) -> Postmortem:
    """Parse LLM response into Postmortem model with AI-labeled sections."""
    sections = parse_markdown_sections(response)

    return Postmortem(
        incident_id=state.incident_id,
        incident_date=state.alert.timestamp,
        severity=state.severity,
        service=state.service,
        summary=PostmortemSection(
            title="Summary",
            content=sections["summary"],
            ai_generated=True,
        ),
        timeline=PostmortemSection(
            title="Timeline",
            content=format_timeline_for_pm(state.timeline),
            ai_generated=False,  # from session state, not LLM
        ),
        root_cause_analysis=PostmortemSection(
            title="Root Cause Analysis",
            content=sections["root_cause_analysis"],
            ai_generated=True,
        ),
        systemic_contributing_factors=PostmortemSection(
            title="Systemic Contributing Factors",
            content=sections["systemic_contributing_factors"],
            ai_generated=True,
        ),
        action_items=parse_action_items(sections["action_items"]),
        resolved_at=state.resolved_at,
        mttr_minutes=compute_mttr(state),
        approved=False,
    )
```

### 9.3 Postmortem display with AI labels

```python
# incident_commander/nodes/interrupt_postmortem.py

def interrupt_postmortem_node(state: IncidentState) -> IncidentState:
    pm = state.postmortem

    for section in [pm.summary, pm.timeline, pm.root_cause_analysis,
                    pm.systemic_contributing_factors]:
        label = "[AI-GENERATED — review carefully]" if section.ai_generated else "[From session data]"
        console.print(Panel(
            section.content,
            title=f"── {section.title} {label} ──",
        ))

    for item in pm.action_items:
        label = "[AI-SUGGESTED]" if item.ai_generated else "[HUMAN-EDITED]"
        console.print(f"  {label} {item.description} — Owner: {item.suggested_owner} — {item.priority}")

    choice = interrupt({
        "prompt": "[a] Approve & save  [e] Edit sections  [r] Regenerate  [q] Quit",
        "postmortem": pm.model_dump(),
    })
    # ... handle choice
```

---

## 10. Runbook retrieval & RAG (FR-7)

### 10.1 In-memory retriever (default, no Qdrant needed)

```python
# incident_commander/tools/rag.py

class InMemoryRetriever:
    """Default retriever for simulation mode. Uses demo runbooks + past incidents."""

    def __init__(self, runbooks: list[dict], past_incidents: list[dict]):
        self._runbooks = runbooks
        self._past_incidents = past_incidents

    def query_runbooks(self, service: str, symptoms: str) -> list[dict]:
        """Keyword-based retrieval from in-memory runbooks."""
        scored = []
        for rb in self._runbooks:
            score = compute_keyword_overlap(f"{service} {symptoms}", rb.get("keywords", []))
            if score > 0:
                scored.append((score, rb))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:5]]

    def query_past_incidents(self, service: str, symptoms: str) -> list[dict]:
        """Keyword-based retrieval from in-memory past incidents."""
        scored = []
        for inc in self._past_incidents:
            score = compute_keyword_overlap(f"{service} {symptoms}", inc.get("keywords", []))
            if score > 0:
                scored.append((score, inc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:5]]
```

### 10.2 Qdrant retriever (optional extra)

```python
# incident_commander/tools/rag.py

class QdrantRetriever:
    """Vector store retriever using Qdrant. Requires ai-incident-commander[rag]."""

    def __init__(self, url: str, collection: str):
        from qdrant_client import QdrantClient
        self._client = QdrantClient(url=url)
        self._collection = collection

    def query_runbooks(self, service: str, symptoms: str) -> list[dict]:
        query_vector = embed(f"{service} {symptoms}")
        results = self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=10,
        )
        return [hit.payload for hit in results if hit.score > 0.5]
```

### 10.3 Retriever protocol (FR-7.4)

```python
from typing import Protocol

class Retriever(Protocol):
    """Injectable retriever protocol for testing and pluggability."""
    def query_runbooks(self, service: str, symptoms: str) -> list[dict]: ...
    def query_past_incidents(self, service: str, symptoms: str) -> list[dict]: ...
```

---

## 11. Cost tracking & LLM observability (FR-8)

### 11.1 CostTracker

```python
# incident_commander/tools/cost.py

class CostTracker:
    """Tracks token usage and estimated cost per LLM call, per session."""

    def __init__(self, pricing: dict[str, dict[str, float]]):
        self._pricing = pricing
        self._calls: list[NodeCost] = []

    def record(
        self,
        node_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> None:
        price = self._pricing.get(model, {"input": 0.0, "output": 0.0})
        cost = (input_tokens / 1_000_000 * price["input"]) + \
               (output_tokens / 1_000_000 * price["output"])

        self._calls.append(NodeCost(
            node_name=node_name,
            llm_model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
        ))

    def report(self, session_id: str) -> CostReport:
        total_in = sum(c.input_tokens for c in self._calls)
        total_out = sum(c.output_tokens for c in self._calls)
        total_cost = sum(c.estimated_cost_usd for c in self._calls)
        models = list(set(c.llm_model for c in self._calls))

        return CostReport(
            session_id=session_id,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_tokens=total_in + total_out,
            total_estimated_cost_usd=total_cost,
            per_node=self._calls,
            models_used=models,
        )
```

### 11.2 LLMObserver (FR-8.5, FR-8.6)

```python
# incident_commander/tools/llm_observer.py
import json
from pathlib import Path

class LLMObserver:
    """Logs every LLM call with prompt, response, tokens, latency. JSONL format."""

    def __init__(self, log_dir: str):
        self._log_path = Path(log_dir) / "llm_calls.jsonl"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        node_name: str,
        model: str,
        prompt: str,
        response: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "node": node_name,
            "model": model,
            "prompt": prompt,
            "response": response,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "latency_ms": latency_ms,
        }
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

### 11.3 LLM router (FR-8.1, FR-8.2)

```python
# incident_commander/tools/llm.py
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
import time

class LLMRouter:
    """Routes LLM calls based on task type. Tracks cost + logs every call."""

    def __init__(self, config: LLMConfig, cost_tracker: CostTracker, observer: LLMObserver):
        self._config = config
        self._cost = cost_tracker
        self._observer = observer
        self._models: dict[str, BaseChatModel] = {}

    def generate(self, prompt: str, task: str, model: str) -> tuple[str, LLMInfo]:
        """Call the LLM and track everything."""
        llm = self._get_model(model)
        start = time.perf_counter()
        response = llm.invoke([HumanMessage(content=prompt)])
        latency_ms = int((time.perf_counter() - start) * 1000)

        info = LLMInfo(
            model=model,
            input_tokens=count_tokens(prompt),
            output_tokens=count_tokens(response.content),
            latency_ms=latency_ms,
        )

        # Track cost
        self._cost.record(
            node_name=task,
            model=model,
            input_tokens=info.input_tokens,
            output_tokens=info.output_tokens,
            latency_ms=latency_ms,
        )

        # Log for observability
        self._observer.log(
            node_name=task,
            model=model,
            prompt=prompt,
            response=response.content,
            input_tokens=info.input_tokens,
            output_tokens=info.output_tokens,
            latency_ms=latency_ms,
        )

        return response.content, info
```

---

## 12. Session persistence (FR-10)

### 12.1 SQLite checkpointer

```python
# incident_commander/persistence/checkpointer.py
from langgraph.checkpoint.sqlite import SqliteSaver
from pathlib import Path
import sqlite3

class SessionManager:
    """Manages incident session persistence via SQLite checkpointer."""

    def __init__(self, session_dir: str):
        self._session_dir = Path(session_dir).expanduser()
        self._session_dir.mkdir(parents=True, exist_ok=True)

    def get_checkpointer(self, thread_id: str) -> SqliteSaver:
        db_path = self._session_dir / f"{thread_id}.db"
        conn = sqlite3.connect(str(db_path))
        return SqliteSaver(conn)

    def list_sessions(self) -> list[dict]:
        """List all saved sessions."""
        sessions = []
        for db_file in self._session_dir.glob("*.db"):
            sessions.append({
                "thread_id": db_file.stem,
                "size_bytes": db_file.stat().st_size,
                "modified": datetime.fromtimestamp(db_file.stat().st_mtime),
            })
        return sessions

    def export_session(self, thread_id: str) -> dict:
        """Export session as JSON (no lock-in)."""
        # Load state from SQLite and serialize
        ...

    def delete_session(self, thread_id: str) -> None:
        """Delete a session."""
        db_path = self._session_dir / f"{thread_id}.db"
        if db_path.exists():
            db_path.unlink()
```

### 12.2 Session export (FR-10.6)

```python
def export_session(self, thread_id: str) -> dict:
    """Export session as JSON — portable, no lock-in."""
    state = self.load_state(thread_id)
    return {
        "thread_id": thread_id,
        "exported_at": datetime.now().isoformat(),
        "state": state.model_dump(),
        "timeline": [e.model_dump() for e in state.timeline],
        "stakeholder_updates": [u.model_dump() for u in state.stakeholder_updates],
        "remediation_suggestions": [r.model_dump() for r in state.remediation_suggestions],
        "postmortem": state.postmortem.model_dump() if state.postmortem else None,
        "cost_report": state.cost_report.model_dump() if state.cost_report else None,
    }
```

---

## 13. Data ingestion & output (FR-9, FR-10)

Since v0.1.0 has no direct PagerDuty/Slack integration, the tool ingests incident data through three interchangeable channels and outputs results as markdown files. All three ingestion channels feed the same `IncidentState` — the tool doesn't know or care where the data came from.

### 13.1 Ingestion channels

```
                 Channel 1: CLI flags (individual files)
                 incident-commander run --alert alert.json --logs ./logs/ ...
                                  │
                 Channel 2: Input directory (markdown files)
                 incident-commander run --input-dir ./incident-2026-001/
                                  │
                 Channel 3: Python API (programmatic)
                 from incident_commander import run_incident
                 result = run_incident(alert=alert_obj, logs=log_list, ...)
                                  │
                                  ▼
                         ┌────────────────┐
                         │ IncidentState  │
                         │ (normalized)    │
                         └────────┬───────┘
                                  │
                          LangGraph processes
                                  │
                                  ▼
                         ┌────────────────┐
                         │ Output writer   │
                         │ (markdown files)│
                         └────────────────┘
```

### 13.2 Channel 1: CLI flags (individual files)

```bash
incident-commander run \
  --alert alert.json \
  --logs ./logs/ \
  --messages messages.json \
  --github prs.json \
  --output-dir ./incident-2026-001-output/
```

Each flag points to a file or directory:
- `--alert` — JSON file with alert data
- `--logs` — directory of log files (`.log`, `.json`, or `.md`)
- `--messages` — JSON file with chat messages export
- `--github` — JSON file with GitHub PR export
- `--output-dir` — where to write output markdown files (default: `./output/<thread_id>/`)

### 13.3 Channel 2: Input directory (markdown + JSON)

```bash
incident-commander run --input-dir ./incident-2026-001/
```

The input directory is a structured folder containing all incident data as markdown and JSON files. This is the primary ingestion mode for teams that export data from their existing tools and drop it into a directory.

#### 13.3.1 Input directory structure

```
incident-2026-001/
├── meta.json              # Incident metadata (required)
├── alert.json             # Alert data (required)
├── logs/
│   ├── 14-03-errors.log   # Log files (any name, .log or .md)
│   ├── 14-07-spike.log
│   └── 14-15-recovery.log
├── messages.json          # Chat messages export
├── github.json            # GitHub PR export
├── runbooks/              # Optional: runbooks specific to this incident
│   ├── db-connection-pool.md
│   └── rollback-procedure.md
└── notes.md               # Optional: commander's manual notes
```

#### 13.3.2 meta.json format

```json
{
  "incident_id": "INC-2026-001",
  "service": "payment-service",
  "severity": "SEV1",
  "start_time": "2026-07-12T14:03:00Z",
  "description": "Payment service outage — DB connection pool exhaustion",
  "commander": "oncall-engineer",
  "oncall_roster": ["engineer-1", "engineer-2", "engineer-3"],
  "tags": ["payment", "database", "production"]
}
```

#### 13.3.3 alert.json format

```json
{
  "severity": "SEV1",
  "service": "payment-service",
  "summary": "Payment service down — 2% of attempts failing",
  "source": "pagerduty",
  "timestamp": "2026-07-12T14:03:00Z",
  "incident_id": "INC-2026-001",
  "metadata": {
    "pagerduty_incident_id": "Q3XY9A",
    "escalation_policy": "payments-team",
    "affected_services": ["checkout", "refund"]
  }
}
```

#### 13.3.4 messages.json format

```json
[
  {
    "timestamp": "2026-07-12T14:04:00Z",
    "author": "jdoe",
    "text": "Looking into the payment outage",
    "channel": "#payments-oncall"
  },
  {
    "timestamp": "2026-07-12T14:09:00Z",
    "author": "asmith",
    "text": "I think it's the connection pool — same symptoms as last month",
    "channel": "#payments-oncall"
  }
]
```

#### 13.3.5 github.json format

```json
[
  {
    "number": 4892,
    "title": "Update payment_processor.py — increase pool size",
    "author": "jdoe",
    "merge_time": "2026-07-12T13:48:00Z",
    "files_changed": ["src/payment_processor.py", "config/pool.yaml"]
  }
]
```

#### 13.3.6 Log file formats

The tool parses both `.log` (plain text) and `.md` (markdown with code blocks) log files:

**Plain log file (`.log`):**
```
2026-07-12T14:03:15Z ERROR payment_processor: Connection pool exhausted (max=50, active=50)
2026-07-12T14:03:16Z ERROR payment_processor: Payment failed — DB connection timeout after 5000ms
2026-07-12T14:07:00Z WARN  metrics: error_rate spike to 2.3% (baseline 0.01%)
```

**Markdown log file (`.md`):**
```markdown
# Error logs — 14:03–14:15

## 14:03 — Connection pool exhaustion
```
2026-07-12T14:03:15Z ERROR payment_processor: Connection pool exhausted (max=50, active=50)
2026-07-12T14:03:16Z ERROR payment_processor: Payment failed — DB connection timeout after 5000ms
```

## 14:07 — Error rate spike
```
2026-07-12T14:07:00Z WARN metrics: error_rate spike to 2.3% (baseline 0.01%)
```
```

#### 13.3.7 notes.md (optional commander notes)

```markdown
# Commander notes — INC-2026-001

## 14:05
First responder: @asmith. Suspects DB connection pool.

## 14:10
Confirmed: connection pool exhausted. PR #4892 increased pool
size but introduced a deadlock in the connection validation logic.

## 14:18
Rolling back PR #4892. Expecting recovery within 2 minutes.
```

Commander notes are parsed as manual timeline events with trust level "low".

#### 13.3.8 Input directory loader

```python
# incident_commander/ingest/input_dir.py
from pathlib import Path
import json

class InputDirLoader:
    """Loads incident data from a structured input directory."""

    def __init__(self, input_dir: str | Path):
        self._dir = Path(input_dir)
        if not self._dir.exists():
            raise FileNotFoundError(f"Input directory not found: {self._dir}")

    def load(self) -> IncidentInput:
        """Load all files from the input directory."""
        meta = self._load_json("meta.json", required=True)
        alert = self._load_json("alert.json", required=True)
        logs = self._load_logs()
        messages = self._load_json("messages.json", required=False, default=[])
        github = self._load_json("github.json", required=False, default=[])
        runbooks = self._load_runbooks()
        notes = self._load_notes()

        return IncidentInput(
            meta=meta,
            alert=Alert(**alert),
            logs=logs,
            messages=[ChatMessage(**m) for m in messages],
            prs=[PR(**pr) for pr in github],
            runbooks=runbooks,
            manual_events=notes,  # parsed from notes.md as timeline events
        )

    def _load_json(self, filename: str, required: bool, default=None) -> Any:
        path = self._dir / filename
        if not path.exists():
            if required:
                raise FileNotFoundError(f"Required file missing: {path}")
            return default
        return json.loads(path.read_text())

    def _load_logs(self) -> list[LogEntry]:
        """Load all log files from logs/ subdirectory."""
        log_dir = self._dir / "logs"
        if not log_dir.exists():
            return []

        entries = []
        for log_file in sorted(log_dir.iterdir()):
            if log_file.suffix in (".log", ".json", ".md"):
                entries.extend(parse_log_file(log_file))
        return entries

    def _load_runbooks(self) -> list[dict]:
        """Load optional runbooks from runbooks/ subdirectory."""
        rb_dir = self._dir / "runbooks"
        if not rb_dir.exists():
            return []

        runbooks = []
        for rb_file in sorted(rb_dir.glob("*.md")):
            runbooks.append({
                "id": rb_file.stem,
                "title": rb_file.stem.replace("-", " ").title(),
                "path": str(rb_file),
                "content": rb_file.read_text(),
                "keywords": extract_keywords(rb_file.read_text()),
            })
        return runbooks

    def _load_notes(self) -> list[TimelineEvent]:
        """Parse commander notes.md into manual timeline events."""
        notes_path = self._dir / "notes.md"
        if not notes_path.exists():
            return []

        notes = notes_path.read_text()
        return parse_notes_to_events(notes)  # each ## heading → timeline event
```

### 13.4 Channel 3: Python API (programmatic ingestion)

For users who want to call the tool from their own scripts, pipelines, or integrations:

```python
# incident_commander/api.py
"""Public Python API for programmatic incident ingestion and output."""

from incident_commander.config import Config
from incident_commander.models import (
    Alert, IncidentState, TimelineEvent, Postmortem, CostReport,
)
from incident_commander.graph import build_graph
from incident_commander.persistence import SessionManager

class IncidentResult:
    """The output of an incident session — returned to the API caller."""
    thread_id: str
    timeline: list[TimelineEvent]
    stakeholder_updates: list[StakeholderUpdate]
    remediation_suggestions: list[RemediationSuggestion]
    postmortem: Postmortem | None
    cost_report: CostReport
    session_dir: str  # where session data was saved

    def to_markdown(self) -> dict[str, str]:
        """Convert all output to markdown files (filename → content)."""
        return {
            "timeline.md": format_timeline_md(self.timeline),
            "stakeholder-updates.md": format_updates_md(self.stakeholder_updates),
            "remediation.md": format_remediation_md(self.remediation_suggestions),
            "postmortem.md": format_postmortem_md(self.postmortem),
            "cost-report.md": format_cost_md(self.cost_report),
            "incident-summary.md": format_summary_md(self),
        }

    def to_json(self) -> dict:
        """Export as JSON (for programmatic consumption)."""
        ...

def run_incident(
    alert: Alert | dict | str,  # Alert object, dict, or path to JSON file
    logs: list[dict] | str | None = None,  # list of log entries or path to log dir
    messages: list[dict] | str | None = None,  # list of messages or path to JSON
    github: list[dict] | str | None = None,  # list of PRs or path to JSON
    runbooks: list[dict] | None = None,  # optional runbooks
    manual_events: list[TimelineEvent] | None = None,  # manual timeline entries
    config: Config | None = None,  # defaults to Config()
    output_dir: str | None = None,  # if set, write markdown output here
    auto_approve: bool = False,  # if True, skip interrupts (for testing/pipelines)
    thread_id: str | None = None,  # resume existing session
) -> IncidentResult:
    """Run the full incident lifecycle programmatically.

    Args:
        alert: Alert data — Alert object, dict, or path to JSON file.
        logs: Log entries — list of dicts or path to log directory.
        messages: Chat messages — list of dicts or path to JSON file.
        github: GitHub PRs — list of dicts or path to JSON file.
        runbooks: Optional runbooks for this incident.
        manual_events: Manually entered timeline events.
        config: Configuration (defaults to Config()).
        output_dir: If set, write markdown output files to this directory.
        auto_approve: If True, auto-approve all interrupts (for pipelines/testing).
        thread_id: Resume an existing session by thread ID.

    Returns:
        IncidentResult with all outputs.

    Example:
        >>> from incident_commander import run_incident, Alert
        >>> result = run_incident(
        ...     alert=Alert(severity="SEV1", service="payment", summary="down",
        ...                 source="manual", timestamp=datetime.now()),
        ...     logs=[{"timestamp": "2026-07-12T14:03:00Z", "level": "ERROR",
        ...           "message": "Connection pool exhausted"}],
        ...     output_dir="./output/",
        ... )
        >>> print(result.postmortem.summary.content)
        >>> print(result.cost_report.total_estimated_cost_usd)
    """
    config = config or Config()

    # Normalize inputs (accept objects, dicts, or file paths)
    alert = _normalize_alert(alert)
    logs = _normalize_logs(logs)
    messages = _normalize_messages(messages)
    github = _normalize_github(github)

    # Build initial state
    thread_id = thread_id or generate_thread_id()
    state = IncidentState(
        alert=alert,
        input_logs=logs,
        input_messages=messages,
        input_prs=github,
        input_runbooks=runbooks or [],
        manual_events=manual_events or [],
        severity=alert.severity,
        service=alert.service,
        incident_id=alert.incident_id,
        thread_id=thread_id,
        mode="run",
    )

    # Build and run graph
    graph = build_graph(config)
    checkpointer = SessionManager(config.session_dir).get_checkpointer(thread_id)

    if auto_approve:
        # Auto-approve all interrupts (for pipelines)
        state = _run_with_auto_approve(graph, state, checkpointer)
    else:
        # Run in foreground — blocks at interrupts
        state = graph.invoke(
            state,
            config={"configurable": {"thread_id": thread_id},
                    "checkpointer": checkpointer},
        )

    # Build result
    result = IncidentResult(
        thread_id=thread_id,
        timeline=state.timeline,
        stakeholder_updates=state.stakeholder_updates,
        remediation_suggestions=state.remediation_suggestions,
        postmortem=state.postmortem,
        cost_report=state.cost_report,
        session_dir=config.session_dir,
    )

    # Write markdown output if requested
    if output_dir:
        write_markdown_output(result, output_dir)

    return result


def run_simulation(
    service: str,
    severity: str,
    scenario: str | None = None,
    seed: int | None = None,
    config: Config | None = None,
    output_dir: str | None = None,
    auto_approve: bool = False,
) -> IncidentResult:
    """Run a simulated incident programmatically.

    Example:
        >>> from incident_commander import run_simulation
        >>> result = run_simulation("payment-service", "SEV1", output_dir="./sim-output/")
    """
    config = config or Config(mode="simulate")

    if scenario:
        sim_data = load_scenario(scenario, seed=seed)
    else:
        sim_data = IncidentSimulator(seed=seed).simulate(service, severity)

    return run_incident(
        alert=sim_data.alert,
        logs=sim_data.logs,
        messages=sim_data.messages,
        github=sim_data.prs,
        runbooks=sim_data.runbooks,
        config=config,
        output_dir=output_dir,
        auto_approve=auto_approve,
    )
```

### 13.5 Output directory (markdown file output)

When `--output-dir` is provided (CLI) or `output_dir` is set (API), the tool writes all output as markdown files to the specified directory.

#### 13.5.1 Output directory structure

```
incident-2026-001-output/
├── incident-summary.md       # Human-readable summary of the entire incident
├── timeline.md               # Full timeline with trust levels + deploy correlations
├── stakeholder-updates.md    # All stakeholder updates (approved drafts)
├── comms-blocks.md           # Pasteable comms blocks (for Slack/email/PagerDuty)
├── remediation.md            # Remediation suggestions with citations + dry-run
├── postmortem.md             # COE-format postmortem with AI section labels
├── cost-report.md            # Per-node cost breakdown + total
├── llm-calls.jsonl           # LLM observability log (JSONL, one line per call)
├── session.json              # Full session export (JSON, for programmatic use)
└── meta.json                 # Session metadata (thread_id, timestamps, models used)
```

#### 13.5.2 Output file formats

**incident-summary.md:**
```markdown
# Incident Summary — INC-2026-001

| Field | Value |
|---|---|
| Incident ID | INC-2026-001 |
| Service | payment-service |
| Severity | SEV1 |
| Start time | 2026-07-12 14:03 UTC |
| Resolved at | 2026-07-12 14:22 UTC |
| MTTR | 19 minutes |
| Deploy correlation | PR #4892 (merged 12 min before alert) |
| Total cost | $0.04 (12,450 tokens) |
| Models used | ollama/qwen2.5-coder:7b |
| Session ID | inc-2026-001-a3b2c1 |

## Key events
- 14:03 — Alert fired (trust: high)
- 13:48 — PR #4892 merged [DEPLOY CORRELATION] (trust: high)
- 14:07 — Error rate spike to 2.3% (trust: medium)
- 14:18 — Rollback initiated (trust: low — human-entered)
- 14:22 — Recovery confirmed (trust: medium)

## Outputs
- [Timeline](timeline.md)
- [Stakeholder updates](stakeholder-updates.md)
- [Comms blocks](comms-blocks.md)
- [Remediation](remediation.md)
- [Postmortem](postmortem.md)
- [Cost report](cost-report.md)
```

**timeline.md:**
```markdown
# Incident Timeline — INC-2026-001

## All events (chronological)

| Time | Source | Event | Trust | Deploy correlation |
|---|---|---|---|---|
| 13:48:00 | github | PR #4892 merged: "Update payment_processor.py" by @jdoe | high | YES (12 min before alert) |
| 14:03:00 | alert | Alert fired: Payment service down — 2% of attempts failing | high | |
| 14:03:15 | log | ERROR: Connection pool exhausted (max=50, active=50) | medium | |
| 14:04:00 | chat | jdoe: Looking into the payment outage | high | |
| 14:07:00 | log | WARN: error_rate spike to 2.3% (baseline 0.01%) | medium | |
| 14:09:00 | chat | asmith: I think it's the connection pool | high | |
| 14:18:00 | manual | Rollback initiated | LOW (human-entered) | |
| 14:22:00 | log | INFO: error_rate back to baseline 0.01% | medium | |

## Deploy correlations
- **PR #4892** — "Update payment_processor.py — increase pool size" by @jdoe
  - Merged at 13:48 (12 minutes before alert)
  - Files changed: src/payment_processor.py, config/pool.yaml
  - Correlation strength: strong (<15 min)
```

**stakeholder-updates.md:**
```markdown
# Stakeholder Updates — INC-2026-001

## Update #1 — 14:05 UTC
**Impact:** 2% of payment attempts failing since 14:03 UTC.
**Root cause:** Suspected DB connection pool exhaustion, potentially triggered
by PR #4892 (merged 12 min before first error).
**Action:** Investigating rollback of PR #4892.
**Next update:** 14:10 UTC (5 min — SEV1 cadence)

## Update #2 — 14:12 UTC
**Impact:** 2% of payment attempts still failing.
**Root cause:** Confirmed — DB connection pool deadlock introduced by PR #4892.
**Action:** Rolling back PR #4892 now.
**Next update:** 14:17 UTC (5 min)

## Update #3 — 14:22 UTC
**Impact:** Payment service recovered. Error rate back to baseline.
**Root cause:** DB connection pool deadlock from PR #4892.
**Action:** Rollback complete. Monitoring for 10 minutes.
**Next update:** 14:32 UTC (if no regression)
```

**comms-blocks.md:**
```markdown
# Pasteable Comms Blocks — INC-2026-001

> Copy-paste these blocks into Slack, email, PagerDuty notes, or wherever
> your team communicates during incidents.

## Update #1 — Incident Notes (for PagerDuty/ticket)

### Timeline
- 14:03 Alert fired (source: PagerDuty, trust: high)
- 13:48 PR #4892 merged (source: GitHub, trust: high, deploy correlation)
- 14:07 Error rate spike (source: logs, trust: medium)

### Remediation
- Suggested: Rollback PR #4892. Confidence: 0.82.
- Source: INC-2025-088 (resolved by rollback)
- Dry-run: Expected outcome — payment success >99% within 2 min

---

## Update #1 — Stakeholder Comms (for Slack/email)

## SEV1 — Payment Service Degradation

**Impact:** 2% of payment attempts failing since 14:03 UTC.
**Root cause:** Suspected DB connection pool exhaustion, potentially
triggered by PR #4892 (merged 12 min before first error).
**Action:** Investigating rollback of PR #4892.
**Next update:** 14:10 UTC (5 minutes).

---

(repeat for each update)
```

**postmortem.md:**
```markdown
# Postmortem — INC-2026-001 — payment-service SEV1

> **Format:** Amazon COE (Correction of Errors)
> **Blameless:** This document focuses on what failed, not who failed.

---

## Summary [AI-GENERATED — review carefully]

On 2026-07-12, the payment service experienced a 19-minute SEV1 outage
affecting 2% of payment attempts. The root cause was a DB connection pool
deadlock introduced by PR #4892, which increased pool size but added a
deadlock in the connection validation logic. The incident was resolved by
rolling back PR #4892.

## Customer Impact [AI-GENERATED — review carefully]

- 2% of payment attempts failed during the 19-minute window
- Estimated 340 affected transactions
- No data corruption; all failed payments were retried successfully post-recovery

## Timeline [From session data]

| Time | Event | Source |
|---|---|---|
| 13:48 | PR #4892 merged | GitHub |
| 14:03 | Alert fired | PagerDuty |
| 14:03 | Connection pool exhausted | logs |
| 14:18 | Rollback initiated | manual |
| 14:22 | Recovery confirmed | logs |

## Root Cause Analysis [AI-GENERATED — review carefully]

PR #4892 modified the connection validation logic in `payment_processor.py`
to add a health check before reusing pooled connections (see 14:03 in
timeline). The health check acquired a lock on the connection pool while
holding a lock on the individual connection, creating a lock-ordering
deadlock under concurrent load...

## Systemic Contributing Factors [AI-GENERATED — review carefully]

1. **No integration test for connection pool under concurrent load.** The
   CI pipeline tested connection pooling in isolation but not under
   concurrent request patterns.
2. **No canary deployment for connection pool changes.** PR #4892 was
   deployed directly to production without a canary stage.
3. **No automated rollback trigger.** The rollback was initiated manually
   15 minutes into the incident. An automated rollback on error-rate
   threshold would have reduced MTTR.

## Action Items

- [ ] Add integration test for connection pool under concurrent load — Owner: Platform Team — P0
- [ ] Implement canary deployment for payment-service config changes — Owner: DevOps Team — P1
- [ ] Add automated rollback on error-rate >1% for 5 minutes — Owner: Platform Team — P1
- [ ] Review all recent connection pool changes for similar deadlock patterns — Owner: Payments Team — P2

---

## AI Section Labels

| Section | AI-generated? |
|---|---|
| Summary | Yes — review carefully |
| Customer Impact | Yes — review carefully |
| Timeline | No — from session data |
| Root Cause Analysis | Yes — review carefully |
| Systemic Contributing Factors | Yes — review carefully |
| Action Items | Yes — owner suggestions are AI-generated |
```

**cost-report.md:**
```markdown
# Cost Report — INC-2026-001

## Summary

| Metric | Value |
|---|---|
| Total input tokens | 8,200 |
| Total output tokens | 4,250 |
| Total tokens | 12,450 |
| Total estimated cost | $0.04 |
| Models used | ollama/qwen2.5-coder:7b |

## Per-node breakdown

| Node | Model | Input tokens | Output tokens | Total | Cost (USD) | Latency (ms) |
|---|---|---|---|---|---|---|
| draft_update | ollama/qwen2.5-coder:7b | 1,200 | 180 | 1,380 | $0.00 | 2,340 |
| draft_update | ollama/qwen2.5-coder:7b | 1,350 | 175 | 1,525 | $0.00 | 2,180 |
| draft_update | ollama/qwen2.5-coder:7b | 1,400 | 170 | 1,570 | $0.00 | 2,250 |
| suggest_remediation | ollama/qwen2.5-coder:7b | 1,800 | 250 | 2,050 | $0.00 | 3,120 |
| dry_run_simulate | ollama/qwen2.5-coder:7b | 1,500 | 220 | 1,720 | $0.00 | 2,890 |
| generate_postmortem | ollama/qwen2.5-coder:7b | 950 | 3,255 | 4,205 | $0.00 | 8,450 |

> Local model (Ollama) = $0.00 per token. Cost shown for transparency.
> Cloud models would incur cost per model pricing.
```

#### 13.5.3 Output writer

```python
# incident_commander/output/markdown_writer.py
from pathlib import Path

class MarkdownOutputWriter:
    """Writes all incident output as markdown files to a directory."""

    def __init__(self, output_dir: str | Path):
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def write_all(self, result: IncidentResult) -> list[Path]:
        """Write all output files. Returns list of file paths written."""
        files = {}

        # Markdown outputs
        files["incident-summary.md"] = format_summary_md(result)
        files["timeline.md"] = format_timeline_md(result.timeline)
        files["stakeholder-updates.md"] = format_updates_md(result.stakeholder_updates)
        files["comms-blocks.md"] = format_comms_blocks_md(result)
        files["remediation.md"] = format_remediation_md(result.remediation_suggestions)
        files["postmortem.md"] = format_postmortem_md(result.postmortem)
        files["cost-report.md"] = format_cost_md(result.cost_report)

        # JSON outputs
        files["session.json"] = json.dumps(result.to_json(), indent=2)
        files["meta.json"] = json.dumps({
            "thread_id": result.thread_id,
            "models_used": result.cost_report.models_used,
            "total_cost_usd": result.cost_report.total_estimated_cost_usd,
            "total_tokens": result.cost_report.total_tokens,
        }, indent=2)

        # LLM observability log (copy from log dir if exists)
        llm_log = find_llm_log(result.session_dir, result.thread_id)
        if llm_log:
            files["llm-calls.jsonl"] = llm_log

        written = []
        for filename, content in files.items():
            path = self._dir / filename
            path.write_text(content)
            written.append(path)

        return written
```

### 13.6 CLI commands (updated)

```bash
# Simulation mode
incident-commander simulate --service <name> --severity <SEV1|SEV2|SEV3> \
  [--scenario <name>] [--seed <int>] \
  [--output-dir <path>] [--auto-approve]

# Real incident — individual files
incident-commander run --alert <alert.json> \
  [--logs <dir>] [--messages <file>] [--github <file>] \
  [--output-dir <path>] [--simulate] [--auto-approve]

# Real incident — input directory (markdown-based)
incident-commander run --input-dir <path> \
  [--output-dir <path>] [--simulate] [--auto-approve]

# View timeline from saved session
incident-commander timeline --thread <thread_id> \
  [--output <file.md>]

# Generate postmortem from saved session
incident-commander postmortem --thread <thread_id> \
  [--model <model_name>] [--output <file.md>]

# Session management
incident-commander sessions list
incident-commander sessions export --thread <thread_id> --output <file.json>
incident-commander sessions delete --thread <thread_id>
```

### 13.7 CLI implementation (updated)

```python
# incident_commander/cli.py
import typer
from rich.console import Console
from pathlib import Path

app = typer.Typer()
console = Console()

@app.command()
def simulate(
    service: str = typer.Option(..., "--service", "-s"),
    severity: str = typer.Option("SEV3", "--severity"),
    scenario: str | None = typer.Option(None, "--scenario"),
    seed: int | None = typer.Option(None, "--seed"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o",
        help="Write markdown output files to this directory"),
    auto_approve: bool = typer.Option(False, "--auto-approve",
        help="Auto-approve all interrupts (for testing/pipelines)"),
):
    """Run a simulated incident — zero credentials needed."""
    from incident_commander.api import run_simulation
    result = run_simulation(
        service=service, severity=severity, scenario=scenario,
        seed=seed, output_dir=output_dir, auto_approve=auto_approve,
    )
    console.print(f"[green]Simulation complete.[/green] Thread: {result.thread_id}")
    if output_dir:
        console.print(f"Output written to: {output_dir}/")


@app.command()
def run(
    alert: str | None = typer.Option(None, "--alert", help="Path to alert JSON"),
    input_dir: str | None = typer.Option(None, "--input-dir", "-i",
        help="Path to structured input directory (meta.json + alert.json + logs/ + ...)"),
    logs: str | None = typer.Option(None, "--logs", help="Path to log directory"),
    messages: str | None = typer.Option(None, "--messages", help="Path to chat export JSON"),
    github: str | None = typer.Option(None, "--github", help="Path to GitHub PR export JSON"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o",
        help="Write markdown output files to this directory"),
    simulate: bool = typer.Option(False, "--simulate",
        help="Run without LLM API key (uses local/mock LLM)"),
    auto_approve: bool = typer.Option(False, "--auto-approve",
        help="Auto-approve all interrupts (for testing/pipelines)"),
):
    """Run the incident commander on a real or simulated alert.

    Two modes:
    1. Individual files: --alert alert.json [--logs ./logs/] [--messages msg.json] [--github prs.json]
    2. Input directory: --input-dir ./incident-2026-001/ (loads all files from directory)
    """
    from incident_commander.api import run_incident
    from incident_commander.ingest import InputDirLoader

    if input_dir:
        # Channel 2: load from input directory
        data = InputDirLoader(input_dir).load()
        result = run_incident(
            alert=data.alert,
            logs=data.logs,
            messages=data.messages,
            github=data.prs,
            runbooks=data.runbooks,
            manual_events=data.manual_events,
            output_dir=output_dir,
            auto_approve=auto_approve,
        )
    elif alert:
        # Channel 1: individual files
        result = run_incident(
            alert=alert,  # path to JSON
            logs=logs,    # path to dir or None
            messages=messages,
            github=github,
            output_dir=output_dir,
            auto_approve=auto_approve,
        )
    else:
        console.print("[red]Error: must provide --alert or --input-dir[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Incident complete.[/green] Thread: {result.thread_id}")
    if output_dir:
        console.print(f"Output written to: {Path(output_dir)}/")


@app.command()
def timeline(
    thread: str = typer.Option(..., "--thread", "-t"),
    output: str | None = typer.Option(None, "--output", "-o",
        help="Write timeline to markdown file instead of stdout"),
):
    """Display or export the timeline for a saved session."""
    config = load_config()
    session = SessionManager(config.session_dir)
    state = session.load_state(thread)

    timeline_md = format_timeline_md(state.timeline)
    if output:
        Path(output).write_text(timeline_md)
        console.print(f"Timeline written to: {output}")
    else:
        console.print(timeline_md)


@app.command()
def postmortem(
    thread: str = typer.Option(..., "--thread", "-t"),
    model: str | None = typer.Option(None, "--model",
        help="Override LLM for regeneration"),
    output: str | None = typer.Option(None, "--output", "-o",
        help="Write postmortem to markdown file instead of stdout"),
):
    """Generate or regenerate a postmortem from a saved session."""
    config = load_config()
    if model:
        config.llm.postmortem_model = model

    session = SessionManager(config.session_dir)
    state = session.load_state(thread)

    # Re-run only the postmortem node
    graph = build_graph(config)
    state = graph.invoke(
        state,
        config={"configurable": {"thread_id": thread}},
        start_node="generate_postmortem",
    )

    pm_md = format_postmortem_md(state.postmortem)
    if output:
        Path(output).write_text(pm_md)
        console.print(f"Postmortem written to: {output}")
    else:
        console.print(pm_md)
```

### 13.8 Foreground CLI interaction (FR-9.6)

The CLI uses `rich` for formatted terminal output and blocks at each interrupt point:

```
$ incident-commander run --input-dir ./incident-2026-001/ --output-dir ./output/

[14:00:00] Loading incident data from: ./incident-2026-001/
[14:00:01] Loaded: 1 alert, 15 logs, 8 messages, 3 PRs, 2 runbooks, 5 manual notes
[14:00:02] Building timeline from 6 sources...
[14:00:03] Timeline: 27 events merged
[14:00:04] Deploy correlation: PR #4892 merged at 13:48 (12 min before alert)
[14:00:05] Retrieving runbooks from knowledge base...
[14:00:06] Reranking 8 evidence items by relevance...
[14:00:07] Timeline complete. Starting update cycle (SEV1: 5 min cadence).

┌── Stakeholder Update Draft #1 ──────────────────────────────┐
│ Impact: 2% of payment attempts failing since 14:03 UTC.     │
│ Root cause: Suspected DB connection pool exhaustion,        │
│ potentially triggered by PR #4892 (merged 12 min before     │
│ first error).                                                │
│ Action: Investigating rollback of PR #4892.                 │
│ Next update: 14:10 UTC (5 min)                               │
└──────────────────────────────────────────────────────────────┘

[a] Approve  [e] Edit  [r] Reject (redraft)  [x] Resolve incident
> _

(blocks here until commander chooses)
```

When `--output-dir` is set, after the session completes:

```
[14:25:00] Incident resolved. Generating postmortem...
[14:25:30] Postmortem generated (COE format, 6 sections, 4 action items).
[14:25:31] Cost report: 12,450 tokens, $0.04 (local model).

[14:25:32] Writing output to: ./output/
[14:25:33]   ✓ incident-summary.md
[14:25:33]   ✓ timeline.md
[14:25:33]   ✓ stakeholder-updates.md
[14:25:33]   ✓ comms-blocks.md
[14:25:33]   ✓ remediation.md
[14:25:33]   ✓ postmortem.md
[14:25:33]   ✓ cost-report.md
[14:25:33]   ✓ llm-calls.jsonl
[14:25:33]   ✓ session.json
[14:25:33]   ✓ meta.json

[green]Done. Session: inc-2026-001-a3b2c1[/green]
```

### 13.9 Auto-approve mode (for pipelines and testing)

When `--auto-approve` is passed (CLI) or `auto_approve=True` (API), the tool skips all interrupts and auto-approves every draft. This is for:

- **CI/CD pipelines** — run the tool as part of an automated incident response pipeline
- **Testing** — run E2E tests without human interaction
- **Batch processing** — process multiple incidents from input directories unattended

```python
# incident_commander/api.py

def _run_with_auto_approve(graph, state, checkpointer) -> IncidentState:
    """Run the graph, auto-approving all interrupts."""
    while True:
        state = graph.invoke(
            state,
            config={"configurable": {"thread_id": state.thread_id},
                    "checkpointer": checkpointer},
        )
        if state.postmortem_approved or state.cost_report:
            break  # reached the end
        # Auto-approve: resume with "approve" at each interrupt
        state = graph.invoke(
            state,
            config={"configurable": {"thread_id": state.thread_id}},
            command=Command(resume="a"),  # auto-approve
        )
    return state
```

### 13.10 Module structure updates

```
incident_commander/
├── ...                         # (existing modules)
├── api.py                      # Public Python API: run_incident, run_simulation
├── schema.py                   # JSON Schema registry, validation, export
├── ingest/
│   ├── __init__.py
│   ├── input_dir.py            # InputDirLoader — loads from structured directory
│   ├── log_parser.py           # Parses .log and .md log files
│   ├── notes_parser.py         # Parses notes.md into timeline events
│   └── normalizer.py           # Normalizes Alert/dict/path inputs to objects
├── models/
│   ├── __init__.py             # Re-exports all models
│   ├── state.py                # IncidentState, Alert, TimelineEvent, etc. (§2)
│   ├── input.py                # ChatMessage, LogEntry, GitHubPR, Runbook, etc. (§13.11.5)
│   └── output.py               # IncidentResult, SessionMeta, LLMCall (§13.11.5)
└── output/
    ├── __init__.py
    ├── markdown_writer.py      # MarkdownOutputWriter — writes all output files
    ├── formatters.py           # format_timeline_md, format_postmortem_md, etc.
    └── comms_blocks.py         # format_comms_blocks_md — pasteable output
```

### 13.11 JSON Schema definitions

This section defines formal JSON Schemas for all input and output types. These schemas:

- Can be used by teams to validate their input data before running the tool
- Are implemented as Pydantic models (§2) — the JSON Schema is auto-generated via `model.model_json_schema()`
- Are informed by **PagerDuty PD-CEF** (Common Event Format) and the **PagerDuty Events API v2** payload structure
- Will serve as the wire format for the v0.2.0 HTTP daemon mode
- Are versioned: `"schema_version": "0.1.0"` in every top-level object

#### 13.11.1 Industry schema alignment — PD-CEF mapping

The tool's `Alert` schema is aligned with PagerDuty's [Common Event Format (PD-CEF)](https://support.pagerduty.com/main/docs/pd-cef), the de facto standard for incident event data. This ensures that teams exporting from PagerDuty (or any PD-CEF-compatible monitoring tool) can map their data to our schema with minimal transformation.

| PD-CEF field | PD-CEF type | PD-CEF required | Our field | Our type | Notes |
|---|---|---|---|---|---|
| `summary` | String | Required | `summary` | String | Direct match |
| `severity` | Enum {info, warning, error, critical} | Required | `severity` | Enum {SEV1, SEV2, SEV3} | We use SRE severity levels (SEV1=critical, SEV2=error, SEV3=warning). `info` is dropped (not actionable for incident commander). |
| `source` | String | Required | `source` | String | Direct match — hostname, service name, or tool name |
| `timestamp` | ISO 8601 | Optional | `timestamp` | ISO 8601 datetime | Required in our schema (we need it for timeline ordering) |
| `component` | String | Optional | `metadata.component` | String | Stored in metadata bag — not all incidents have a clear component |
| `group` | String | Optional | `metadata.group` | String | Stored in metadata bag |
| `class` | String | Optional | `metadata.event_class` | String | Stored in metadata bag (renamed — `class` is a Python reserved word) |
| `custom_details` | Object | Optional | `metadata.custom_details` | Object | Stored in metadata bag — free-form key-value pairs |

**Divergences from PD-CEF (intentional):**

1. **Severity mapping:** We use `SEV1/SEV2/SEV3` instead of `info/warning/error/critical` because our tool is incident-focused (not alert-focused). `info` severity events are not incidents.
2. **`service` field (added):** PD-CEF doesn't have a dedicated service field — it's often embedded in `source` or `custom_details`. We promote it to a top-level required field because our entire workflow is service-oriented (timeline, deploy correlation, runbook retrieval all key off service).
3. **`incident_id` field (added):** PD-CEF events don't carry an incident ID (PagerDuty assigns it). Since we ingest from files/API, we need the caller to provide it.
4. **`metadata` bag:** All PD-CEF optional fields (`component`, `group`, `class`, `custom_details`) are stored in a single `metadata` dict to keep the top-level schema clean and extensible.

#### 13.11.2 Input schemas

**Alert schema (input)** — `alert.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/alert.json",
  "title": "Alert",
  "description": "Parsed alert from JSON input. Aligned with PagerDuty PD-CEF.",
  "type": "object",
  "required": ["severity", "service", "summary", "timestamp"],
  "properties": {
    "severity": {
      "type": "string",
      "enum": ["SEV1", "SEV2", "SEV3"],
      "description": "SEV1=critical (customer impact), SEV2=major degradation, SEV3=minor degradation"
    },
    "service": {
      "type": "string",
      "minLength": 1,
      "description": "Affected service name (e.g., 'payment-service')"
    },
    "summary": {
      "type": "string",
      "minLength": 1,
      "description": "High-level text summary of the event (PD-CEF 'summary')"
    },
    "source": {
      "type": "string",
      "default": "manual",
      "description": "Source system — 'pagerduty', 'manual', 'simulated', or monitoring tool name (PD-CEF 'source')"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp when the event was detected (PD-CEF 'timestamp')"
    },
    "incident_id": {
      "type": "string",
      "default": "",
      "description": "Incident identifier from source system (e.g., PagerDuty incident ID)"
    },
    "metadata": {
      "type": "object",
      "description": "PD-CEF optional fields + free-form metadata",
      "properties": {
        "component": { "type": "string", "description": "Affected component (PD-CEF 'component')" },
        "group": { "type": "string", "description": "Cluster/grouping of sources (PD-CEF 'group')" },
        "event_class": { "type": "string", "description": "Event class/type (PD-CEF 'class', renamed to avoid Python keyword)" },
        "custom_details": { "type": "object", "description": "Free-form key-value details (PD-CEF 'custom_details')" },
        "pagerduty_incident_id": { "type": "string" },
        "escalation_policy": { "type": "string" },
        "affected_services": { "type": "array", "items": { "type": "string" } }
      },
      "additionalProperties": true
    }
  },
  "additionalProperties": false
}
```

**ChatMessage schema** — `messages.json` (array of these)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/chat-message.json",
  "title": "ChatMessage",
  "description": "A chat message from Slack, Teams, or other chat export.",
  "type": "object",
  "required": ["timestamp", "author", "text"],
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "When the message was sent"
    },
    "author": {
      "type": "string",
      "minLength": 1,
      "description": "Message author (username, display name, or email)"
    },
    "text": {
      "type": "string",
      "minLength": 1,
      "description": "Message content"
    },
    "channel": {
      "type": "string",
      "default": "",
      "description": "Channel or room name (e.g., '#payments-oncall')"
    },
    "thread_ts": {
      "type": "string",
      "default": "",
      "description": "Thread timestamp for Slack threaded messages"
    }
  },
  "additionalProperties": true
}
```

**LogEntry schema** — parsed from `.log`, `.json`, or `.md` log files

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/log-entry.json",
  "title": "LogEntry",
  "description": "A single parsed log entry.",
  "type": "object",
  "required": ["timestamp", "level", "message"],
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Log entry timestamp"
    },
    "level": {
      "type": "string",
      "enum": ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "TRACE"],
      "description": "Log level"
    },
    "message": {
      "type": "string",
      "description": "Log message content"
    },
    "source": {
      "type": "string",
      "default": "",
      "description": "Logger name or source file"
    },
    "metadata": {
      "type": "object",
      "description": "Additional structured log fields (request_id, trace_id, etc.)",
      "additionalProperties": true
    }
  },
  "additionalProperties": false
}
```

**GitHubPR schema** — `github.json` (array of these)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/github-pr.json",
  "title": "GitHubPR",
  "description": "A GitHub pull request export for deploy correlation.",
  "type": "object",
  "required": ["number", "title", "author", "merge_time"],
  "properties": {
    "number": {
      "type": "integer",
      "minimum": 1,
      "description": "PR number"
    },
    "title": {
      "type": "string",
      "description": "PR title"
    },
    "author": {
      "type": "string",
      "description": "PR author username"
    },
    "merge_time": {
      "type": "string",
      "format": "date-time",
      "description": "When the PR was merged (ISO 8601)"
    },
    "files_changed": {
      "type": "array",
      "items": { "type": "string" },
      "default": [],
      "description": "List of file paths changed in the PR"
    },
    "labels": {
      "type": "array",
      "items": { "type": "string" },
      "default": [],
      "description": "PR labels"
    },
    "base_branch": {
      "type": "string",
      "default": "main",
      "description": "Target branch"
    }
  },
  "additionalProperties": true
}
```

**Runbook schema** — from `runbooks/` directory or API input

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/runbook.json",
  "title": "Runbook",
  "description": "A runbook for incident response procedures.",
  "type": "object",
  "required": ["title", "content"],
  "properties": {
    "id": {
      "type": "string",
      "description": "Runbook identifier (filename stem or provided ID)"
    },
    "title": {
      "type": "string",
      "description": "Human-readable title"
    },
    "path": {
      "type": "string",
      "description": "File path (if loaded from disk)"
    },
    "content": {
      "type": "string",
      "description": "Full markdown content of the runbook"
    },
    "keywords": {
      "type": "array",
      "items": { "type": "string" },
      "default": [],
      "description": "Extracted keywords for RAG retrieval"
    },
    "service": {
      "type": "string",
      "default": "",
      "description": "Service this runbook applies to (if specific)"
    }
  },
  "additionalProperties": true
}
```

**IncidentMeta schema** — `meta.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/incident-meta.json",
  "title": "IncidentMeta",
  "description": "Incident metadata for the input directory.",
  "type": "object",
  "required": ["incident_id", "service", "severity", "start_time"],
  "properties": {
    "incident_id": {
      "type": "string",
      "description": "Unique incident identifier"
    },
    "service": {
      "type": "string",
      "description": "Primary affected service"
    },
    "severity": {
      "type": "string",
      "enum": ["SEV1", "SEV2", "SEV3"]
    },
    "start_time": {
      "type": "string",
      "format": "date-time",
      "description": "Incident start time"
    },
    "description": {
      "type": "string",
      "default": "",
      "description": "Human-readable incident description"
    },
    "commander": {
      "type": "string",
      "default": "",
      "description": "Incident commander name/username"
    },
    "oncall_roster": {
      "type": "array",
      "items": { "type": "string" },
      "default": [],
      "description": "On-call engineers for this incident"
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "default": [],
      "description": "Tags for categorization"
    }
  },
  "additionalProperties": true
}
```

**IncidentInput schema** — aggregate input (used by Python API)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/incident-input.json",
  "title": "IncidentInput",
  "description": "Aggregate input for run_incident() — all data needed to process an incident.",
  "type": "object",
  "required": ["alert"],
  "properties": {
    "schema_version": { "type": "string", "default": "0.1.0" },
    "alert": { "$ref": "https://incident-commander.ai/schema/0.1.0/alert.json" },
    "logs": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/log-entry.json" },
      "default": []
    },
    "messages": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/chat-message.json" },
      "default": []
    },
    "github": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/github-pr.json" },
      "default": []
    },
    "runbooks": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/runbook.json" },
      "default": []
    },
    "manual_events": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/timeline-event.json" },
      "default": [],
      "description": "Manually entered timeline events (from notes.md or API)"
    },
    "meta": { "$ref": "https://incident-commander.ai/schema/0.1.0/incident-meta.json" }
  },
  "additionalProperties": false
}
```

#### 13.11.3 Output schemas

**TimelineEvent schema** — output (also used for manual input events)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/timeline-event.json",
  "title": "TimelineEvent",
  "description": "A single event in the incident timeline.",
  "type": "object",
  "required": ["timestamp", "source", "event_type", "content", "trust_level"],
  "properties": {
    "timestamp": { "type": "string", "format": "date-time" },
    "source": {
      "type": "string",
      "enum": ["alert", "chat", "log", "github", "manual"],
      "description": "Where the event came from"
    },
    "event_type": {
      "type": "string",
      "description": "Event type: 'alert_fired', 'error_spike', 'pr_merged', 'message', 'manual_note', etc."
    },
    "content": { "type": "string", "description": "Human-readable event content" },
    "trust_level": {
      "type": "string",
      "enum": ["high", "medium", "low"],
      "description": "Trust level: high=PagerDuty/GitHub, medium=logs, low=human-entered"
    },
    "deploy_correlation": {
      "type": "boolean",
      "default": false,
      "description": "True if within deploy correlation window of alert"
    }
  },
  "additionalProperties": false
}
```

**StakeholderUpdate schema** — output

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/stakeholder-update.json",
  "title": "StakeholderUpdate",
  "description": "A drafted stakeholder update in consequence-first format.",
  "type": "object",
  "required": ["update_number", "impact", "root_cause_hypothesis", "action", "next_update_time", "timestamp"],
  "properties": {
    "update_number": { "type": "integer", "minimum": 1 },
    "impact": { "type": "string", "description": "What's broken, who's affected" },
    "root_cause_hypothesis": { "type": "string", "description": "Current best guess" },
    "action": { "type": "string", "description": "What we're doing about it" },
    "next_update_time": { "type": "string", "format": "date-time" },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1, "default": 1.0 },
    "approved": { "type": "boolean", "default": false },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

**RemediationSuggestion schema** — output

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/remediation-suggestion.json",
  "title": "RemediationSuggestion",
  "description": "A remediation suggestion with citation and dry-run outcome.",
  "type": "object",
  "required": ["action", "citation", "confidence", "dry_run_outcome"],
  "properties": {
    "action": { "type": "string", "description": "Suggested action (e.g., 'Rollback PR #4892')" },
    "citation": { "type": "string", "description": "Source reference (e.g., 'Source: incident INC-2025-088')" },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "dry_run_outcome": { "type": "string", "description": "LLM-simulated expected outcome (not real execution)" },
    "similar_incidents": {
      "type": "array",
      "items": { "type": "string" },
      "default": [],
      "description": "Past incident IDs with similar patterns"
    },
    "approved": { "type": "boolean", "default": false }
  },
  "additionalProperties": false
}
```

**DeployCorrelation schema** — output

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/deploy-correlation.json",
  "title": "DeployCorrelation",
  "description": "A GitHub PR/commit correlated with the incident.",
  "type": "object",
  "required": ["pr_number", "pr_title", "author", "merge_time", "minutes_before_alert"],
  "properties": {
    "pr_number": { "type": "integer", "minimum": 1 },
    "pr_title": { "type": "string" },
    "author": { "type": "string" },
    "merge_time": { "type": "string", "format": "date-time" },
    "files_changed": { "type": "array", "items": { "type": "string" }, "default": [] },
    "minutes_before_alert": { "type": "integer", "description": "How many minutes before alert fired" },
    "correlation_strength": {
      "type": "string",
      "enum": ["strong", "weak"],
      "default": "strong",
      "description": "strong = <15 min before alert, weak = <30 min"
    }
  },
  "additionalProperties": false
}
```

**Postmortem schema (COE format)** — output

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/postmortem.json",
  "title": "Postmortem",
  "description": "Amazon COE (Correction of Errors) format postmortem.",
  "type": "object",
  "required": ["incident_id", "incident_date", "severity", "service", "summary", "timeline", "root_cause_analysis", "systemic_contributing_factors", "action_items"],
  "properties": {
    "incident_id": { "type": "string" },
    "incident_date": { "type": "string", "format": "date-time" },
    "severity": { "type": "string" },
    "service": { "type": "string" },
    "summary": { "$ref": "#/$defs/postmortemSection" },
    "customer_impact": { "$ref": "#/$defs/postmortemSection" },
    "stakeholder_communication_log": { "$ref": "#/$defs/postmortemSection" },
    "regulatory_compliance_impact": { "$ref": "#/$defs/postmortemSection" },
    "timeline": { "$ref": "#/$defs/postmortemSection" },
    "root_cause_analysis": { "$ref": "#/$defs/postmortemSection" },
    "systemic_contributing_factors": { "$ref": "#/$defs/postmortemSection" },
    "action_items": {
      "type": "array",
      "items": { "$ref": "#/$defs/actionItem" }
    },
    "resolved_at": { "type": ["string", "null"], "format": "date-time" },
    "mttr_minutes": { "type": ["integer", "null"] },
    "approved": { "type": "boolean", "default": false }
  },
  "$defs": {
    "postmortemSection": {
      "type": "object",
      "required": ["title", "content", "ai_generated"],
      "properties": {
        "title": { "type": "string" },
        "content": { "type": "string" },
        "ai_generated": { "type": "boolean", "description": "True = LLM wrote this, False = human wrote/edited" }
      },
      "additionalProperties": false
    },
    "actionItem": {
      "type": "object",
      "required": ["description", "suggested_owner"],
      "properties": {
        "description": { "type": "string" },
        "suggested_owner": { "type": "string" },
        "priority": { "type": "string", "enum": ["P0", "P1", "P2"], "default": "P1" },
        "ai_generated": { "type": "boolean", "default": true }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

**CostReport schema** — output

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/cost-report.json",
  "title": "CostReport",
  "description": "Aggregate cost report for an incident session.",
  "type": "object",
  "required": ["session_id", "total_input_tokens", "total_output_tokens", "total_tokens", "total_estimated_cost_usd", "per_node", "models_used"],
  "properties": {
    "session_id": { "type": "string" },
    "total_input_tokens": { "type": "integer", "minimum": 0 },
    "total_output_tokens": { "type": "integer", "minimum": 0 },
    "total_tokens": { "type": "integer", "minimum": 0 },
    "total_estimated_cost_usd": { "type": "number", "minimum": 0 },
    "per_node": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["node_name", "llm_model", "input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd", "latency_ms"],
        "properties": {
          "node_name": { "type": "string" },
          "llm_model": { "type": "string" },
          "input_tokens": { "type": "integer", "minimum": 0 },
          "output_tokens": { "type": "integer", "minimum": 0 },
          "total_tokens": { "type": "integer", "minimum": 0 },
          "estimated_cost_usd": { "type": "number", "minimum": 0 },
          "latency_ms": { "type": "integer", "minimum": 0 }
        },
        "additionalProperties": false
      }
    },
    "models_used": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "additionalProperties": false
}
```

**IncidentResult schema** — aggregate output (returned by `run_incident()`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/incident-result.json",
  "title": "IncidentResult",
  "description": "The complete output of an incident session.",
  "type": "object",
  "required": ["thread_id", "timeline", "stakeholder_updates", "remediation_suggestions", "cost_report", "schema_version"],
  "properties": {
    "schema_version": { "type": "string", "default": "0.1.0" },
    "thread_id": { "type": "string", "description": "Session thread ID" },
    "timeline": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/timeline-event.json" }
    },
    "stakeholder_updates": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/stakeholder-update.json" }
    },
    "remediation_suggestions": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/remediation-suggestion.json" }
    },
    "deploy_correlations": {
      "type": "array",
      "items": { "$ref": "https://incident-commander.ai/schema/0.1.0/deploy-correlation.json" },
      "default": []
    },
    "postmortem": {
      "oneOf": [
        { "$ref": "https://incident-commander.ai/schema/0.1.0/postmortem.json" },
        { "type": "null" }
      ],
      "default": null
    },
    "cost_report": { "$ref": "https://incident-commander.ai/schema/0.1.0/cost-report.json" },
    "session_dir": { "type": "string", "description": "Where session data was saved" }
  },
  "additionalProperties": false
}
```

**SessionMeta schema** — `meta.json` in output directory

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/session-meta.json",
  "title": "SessionMeta",
  "description": "Session metadata written to output directory.",
  "type": "object",
  "required": ["thread_id"],
  "properties": {
    "thread_id": { "type": "string" },
    "models_used": { "type": "array", "items": { "type": "string" }, "default": [] },
    "total_cost_usd": { "type": "number", "minimum": 0, "default": 0 },
    "total_tokens": { "type": "integer", "minimum": 0, "default": 0 },
    "started_at": { "type": "string", "format": "date-time" },
    "ended_at": { "type": "string", "format": "date-time" },
    "mode": { "type": "string", "enum": ["simulate", "run"] },
    "auto_approved": { "type": "boolean", "default": false }
  },
  "additionalProperties": true
}
```

**LLM call record schema** — `llm-calls.jsonl` (one JSON object per line)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://incident-commander.ai/schema/0.1.0/llm-call.json",
  "title": "LLMCall",
  "description": "A single LLM API call record for observability (one per line in llm-calls.jsonl).",
  "type": "object",
  "required": ["call_id", "timestamp", "node_name", "model", "input_tokens", "output_tokens", "latency_ms"],
  "properties": {
    "call_id": { "type": "string", "description": "Unique call identifier" },
    "timestamp": { "type": "string", "format": "date-time" },
    "node_name": { "type": "string", "description": "Which graph node made this call" },
    "model": { "type": "string", "description": "LLM model used" },
    "input_tokens": { "type": "integer", "minimum": 0 },
    "output_tokens": { "type": "integer", "minimum": 0 },
    "total_tokens": { "type": "integer", "minimum": 0 },
    "estimated_cost_usd": { "type": "number", "minimum": 0, "default": 0 },
    "latency_ms": { "type": "integer", "minimum": 0 },
    "prompt_hash": { "type": "string", "description": "SHA-256 hash of prompt (for dedup analysis), not the full prompt" },
    "response_truncated": { "type": "boolean", "default": false },
    "error": { "type": ["string", "null"], "default": null, "description": "Error message if call failed" }
  },
  "additionalProperties": true
}
```

#### 13.11.4 Schema validation

Schemas are validated at runtime using Pydantic's built-in validation. The JSON Schema definitions above are auto-generated from the Pydantic models in §2 using `model.model_json_schema()`.

```python
# incident_commander/schema.py
"""Schema validation and JSON Schema export."""
from pathlib import Path
from incident_commander.models import (
    Alert, ChatMessage, LogEntry, GitHubPR, Runbook,
    IncidentMeta, IncidentInput, IncidentResult,
    TimelineEvent, StakeholderUpdate, RemediationSuggestion,
    DeployCorrelation, Postmortem, CostReport, SessionMeta, LLMCall,
)

SCHEMA_VERSION = "0.1.0"

# Registry of all schemas for export
SCHEMAS: dict[str, type] = {
    "alert": Alert,
    "chat-message": ChatMessage,
    "log-entry": LogEntry,
    "github-pr": GitHubPR,
    "runbook": Runbook,
    "incident-meta": IncidentMeta,
    "incident-input": IncidentInput,
    "incident-result": IncidentResult,
    "timeline-event": TimelineEvent,
    "stakeholder-update": StakeholderUpdate,
    "remediation-suggestion": RemediationSuggestion,
    "deploy-correlation": DeployCorrelation,
    "postmortem": Postmortem,
    "cost-report": CostReport,
    "session-meta": SessionMeta,
    "llm-call": LLMCall,
}

def export_schemas(output_dir: str | Path) -> list[Path]:
    """Export all JSON Schemas to files. Useful for documentation and external consumers."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in SCHEMAS.items():
        schema = model.model_json_schema()
        schema["$id"] = f"https://incident-commander.ai/schema/{SCHEMA_VERSION}/{name}.json"
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        path = output_dir / f"{name}.json"
        path.write_text(json.dumps(schema, indent=2))
        written.append(path)
    return written

def validate_input(data: dict, schema_name: str) -> bool:
    """Validate a dict against a named schema. Raises ValidationError on failure."""
    model = SCHEMAS[schema_name]
    model(**data)  # Raises pydantic.ValidationError if invalid
    return True
```

**CLI schema export:**

```bash
# Export all JSON Schemas to a directory
incident-commander export-schemas --output-dir ./schemas/

# Validate an alert file before running
incident-commander validate --alert alert.json --schema alert
```

**Python API schema access:**

```python
from incident_commander.schema import SCHEMAS, export_schemas, validate_input

# Get the JSON Schema for any model
alert_schema = SCHEMAS["alert"].model_json_schema()

# Validate input data
validate_input({"severity": "SEV1", "service": "payment", "summary": "down",
                "timestamp": "2026-07-12T14:03:00Z"}, "alert")  # → True

# Export all schemas to disk
export_schemas("./schemas/")
```

#### 13.11.5 New Pydantic models (not in §2)

The following models are referenced in the schemas above but were not defined in §2. They are defined here:

```python
# incident_commander/models/input.py

class ChatMessage(BaseModel):
    """A chat message from Slack, Teams, or other chat export."""
    timestamp: datetime
    author: str
    text: str
    channel: str = ""
    thread_ts: str = ""

class LogEntry(BaseModel):
    """A single parsed log entry."""
    timestamp: datetime
    level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "TRACE"]
    message: str
    source: str = ""
    metadata: dict = Field(default_factory=dict)

class GitHubPR(BaseModel):
    """A GitHub pull request for deploy correlation."""
    number: int
    title: str
    author: str
    merge_time: datetime
    files_changed: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    base_branch: str = "main"

class Runbook(BaseModel):
    """A runbook for incident response."""
    id: str = ""
    title: str
    path: str = ""
    content: str
    keywords: list[str] = Field(default_factory=list)
    service: str = ""

class IncidentMeta(BaseModel):
    """Incident metadata from meta.json."""
    incident_id: str
    service: str
    severity: Literal["SEV1", "SEV2", "SEV3"]
    start_time: datetime
    description: str = ""
    commander: str = ""
    oncall_roster: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

class IncidentInput(BaseModel):
    """Aggregate input for run_incident()."""
    schema_version: str = "0.1.0"
    alert: Alert
    logs: list[LogEntry] = Field(default_factory=list)
    messages: list[ChatMessage] = Field(default_factory=list)
    github: list[GitHubPR] = Field(default_factory=list)
    runbooks: list[Runbook] = Field(default_factory=list)
    manual_events: list[TimelineEvent] = Field(default_factory=list)
    meta: Optional[IncidentMeta] = None

# incident_commander/models/output.py

class SessionMeta(BaseModel):
    """Session metadata written to output directory."""
    thread_id: str
    models_used: list[str] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    mode: Literal["simulate", "run"] = "simulate"
    auto_approved: bool = False

class LLMCall(BaseModel):
    """A single LLM API call record (one per line in llm-calls.jsonl)."""
    call_id: str
    timestamp: datetime
    node_name: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float = 0.0
    latency_ms: int
    prompt_hash: str = ""
    response_truncated: bool = False
    error: Optional[str] = None
```

---

## 14. Safety guardrails implementation

### 14.1 Guardrail summary (maps to PRD threats T1-T7)

| Guardrail | PRD ref | SPEC impl | How it works |
|---|---|---|---|
| Human approval before all output | T1, T3, C6 | §3.3, §3.4 | LangGraph `interrupt()` at 3 points: update, remediation, postmortem. Graph blocks. |
| Confidence threshold | T1, FR-4.7, FR-5.6 | §7.1, §8.1 | LLM includes confidence in response. If < threshold (default 0.7), suggestion suppressed or warning displayed. |
| Source citations required | T1, FR-5.2 | §8.1 | Prompt requires "Citation: Source: ...". If missing, suggestion rejected. |
| No execution capability | T4, NG1, FR-5.5 | §1.1 | Architecture has no execution nodes. Tool only drafts, suggests, and dry-runs. Dry-run is LLM simulation, not code execution. |
| AI section labeling | C7, FR-6.4 | §9.2, §9.3 | Every postmortem section has `ai_generated: bool`. Displayed as `[AI-GENERATED]` or `[From session data]`. |
| Blameless framing | FR-6.3 | §9.1 | Prompt explicitly says "BLAMELESS — focus on what failed, not who failed." Systemic factors section. |
| Local LLM default | T2, C8 | §11.3 | Default config uses `ollama/qwen2.5-coder:7b`. Cloud models opt-in only. |
| No telemetry | C3 | §13 | No analytics, no phone-home, no usage reporting. Period. |
| Session data local | T6, FR-10.5 | §12 | SQLite files in `~/.incident-commander/sessions/`. No cloud sync. |

### 14.2 Dry-run safety (FR-5.7)

The dry-run is an **LLM simulation**, not code execution:

```python
def dry_run_simulate_node(state: IncidentState) -> IncidentState:
    """Simulate remediation outcome via LLM. NOT code execution."""
    # This node calls the LLM to predict what would happen.
    # It does NOT run any code, make any API calls, or execute anything.
    # The "simulation" is a text prediction, not a real simulation.

    prompt = DRY_RUN_PROMPT.format(
        action=state.current_remediation.action,
        service=state.service,
        error_rate=extract_error_rate(state.timeline),
        timeline_summary=format_timeline_summary(state.timeline),
    )

    response, info = llm_router.generate(
        prompt=prompt,
        task="dry_run_simulation",
        model=config.llm.analysis_model,
    )

    state.current_remediation.dry_run_outcome = response
    return state
```

---

## 15. Edge case handling (maps to PRD §13)

| Edge case | SPEC handling | Node(s) affected |
|---|---|---|
| E1: 24h+ incident | Session persisted in SQLite. `run --thread <id>` resumes. State includes all prior updates + timeline. | `receive_alert` (resume mode) |
| E2: Concurrent incidents | v0.1.0: separate sessions, separate thread IDs, separate SQLite DBs. No shared state. | All (session isolation) |
| E3: LLM failure mid-draft | `LLMRouter.generate()` catches exceptions. Logs error. Displays "LLM failed — please write manually." Continues cadence cycle. | `draft_update`, `suggest_remediation`, `generate_postmortem` |
| E4: Empty knowledge base | `retrieve_runbooks` returns empty list. `suggest_remediation` states "No historical data available." Remediation disabled, continues to postmortem. | `retrieve_runbooks`, `suggest_remediation` |
| E5: Commander disconnect | Session state persisted at each interrupt. `run --thread <id>` resumes from last checkpoint. | `interrupt_*` nodes |
| E6: No deploy correlation | `correlate_deploys` returns empty list. Timeline has no deploy markers. Stated: "No recent deploys correlated." | `correlate_deploys` |
| E7: All sources unavailable | `build_timeline` creates timeline with only the alert event. Stated: "No external sources available." | `build_timeline` |
| E8: Very long timeline (500+) | `format_timeline` paginates: 50 events per page. Summary view shows first/last 5 + count. | `build_timeline` (display) |
| E9: All suggestions below threshold | `suggest_remediation` states "No high-confidence suggestions. Consider lowering threshold." Continues to postmortem. | `suggest_remediation` |
| E10: Postmortem regeneration with different LLM | `postmortem --thread <id> --model <name>` re-runs `generate_postmortem` with different model. Previous draft saved as version. | `generate_postmortem`, CLI |

---

## 16. LLM strategy

### 16.1 Model routing

| Task | Default model | Rationale | Cloud alternative |
|---|---|---|---|
| Timeline construction | None (deterministic) | No LLM needed — just sorting and merging | N/A |
| Deploy correlation | None (deterministic) | No LLM needed — timestamp comparison | N/A |
| Evidence reranking | None (deterministic) | Keyword overlap + scoring — no LLM needed | N/A |
| Stakeholder update drafting | Local (OMLX/Ollama Qwen) | Most frequent call; local = zero cost | gpt-4o-mini (cheap, fast) |
| Remediation suggestion | Local (OMLX/Ollama Qwen) | Pattern matching from retrieved data | gpt-4o (better reasoning) |
| Dry-run simulation | Local (OMLX/Ollama Qwen) | Text prediction, not code execution | gpt-4o |
| Postmortem generation | Cloud (if available) or local | Long-form generation; cloud quality better | claude-3-5-sonnet, gpt-4o |

### 16.2 Cost optimization

- Local LLM for high-frequency tasks (stakeholder updates every 5 min)
- Cloud LLM only for one-time tasks (postmortem) — opt-in
- Simulation mode can run with local LLM only — zero API cost
- Cost report makes every session's cost transparent

---

## 17. Testing plan

### 17.1 Test layers

| Layer | Scope | What it validates | Location | CI? |
|---|---|---|---|---|
| **Unit** | Individual components: models, timeline engine, deploy correlation, simulator, cost tracker, LLM observer, reranker, pasteable output formatter | Each component works in isolation; edge cases | `tests/unit/` | Yes |
| **Integration** | LangGraph nodes with mocked LLM + mocked retriever; CLI commands; interrupt flows; session persistence; cost tracking across nodes | Components work together; state transitions correct; graph wiring correct | `tests/integration/` | Yes |
| **E2E** | Full incident lifecycle on simulated alert; all interrupt points; cost report produced; LLM logs recorded; pasteable output generated; session saved + resumed | The end-to-end user journey works | `tests/e2e/` | Yes |
| **Field study** | Real LLM on pre-built scenarios; content quality assessment | AI-generated content quality, timeline accuracy, postmortem usefulness, cost per session | `docs/field-study.md` | No (manual) |

### 17.2 Unit tests

#### 17.2.1 Test file map

| File | Component | Key test cases |
|---|---|---|
| `tests/unit/test_models.py` | All Pydantic models | `Alert` accepts valid severity, rejects invalid. `TimelineEvent` trust level assignment. `IncidentState` defaults. `StakeholderUpdate` fields. `Postmortem` COE structure. `CostReport` aggregation. `ActionItem` priority validation. `DeployCorrelation` strength calc. |
| `tests/unit/test_timeline.py` | `build_timeline_node` logic | Multi-source merge (alert + log + chat + github). Chronological ordering. Trust level assignment per source. Human-entered events flagged low. Deploy correlation marker applied. Empty sources → timeline with only alert. 500+ events → pagination. |
| `tests/unit/test_deploy_correlation.py` | `correlate_deploys_node` logic | PR within 30 min → strong/weak correlation. PR outside window → no correlation. PR after alert → no correlation. Multiple PRs → sorted by minutes_before_alert. Empty PR list → no correlations. |
| `tests/unit/test_simulation.py` | `IncidentSimulator` | Generates valid alert with correct severity. Generates N logs. Generates N messages. Generates N PRs. Seeded random produces identical output. Zero credentials needed. All 8 pre-built scenarios load correctly. |
| `tests/unit/test_scenarios.py` | Pre-built scenario library | All 8 scenarios have valid config. Each scenario produces a coherent incident. SEV1/SEV2/SEV3 scenarios present. Deploy-correlated and non-correlated scenarios present. |
| `tests/unit/test_reranker.py` | `rerank_evidence_node` logic | Keyword overlap scoring. Recency scoring. Severity match scoring. Combined score ordering. Empty evidence → empty result. 50 documents → top 10 returned. |
| `tests/unit/test_cost_tracker.py` | `CostTracker` | Single call recorded correctly. Multiple calls aggregated. Per-node breakdown accurate. Total tokens = sum of input + output. Local model (pricing 0.0) → zero cost. Cloud model → correct pricing. Empty calls → zero report. |
| `tests/unit/test_llm_observer.py` | `LLMObserver` | Log entry written to JSONL. All fields present (node, model, prompt, response, tokens, latency). Multiple calls → multiple lines. File created if not exists. |
| `tests/unit/test_pasteable.py` | `produce_output_node` formatting | Incident notes block format correct. Comms block format correct. Both blocks contain update content. Blocks are valid markdown. Severity displayed in comms block. |
| `tests/unit/test_postmortem_format.py` | Postmortem COE parsing | LLM response parsed into correct sections. Summary section extracted. Root cause analysis extracted. Systemic contributing factors extracted. Action items parsed with owner + priority. AI-generated flag set correctly on all sections. Timeline section flagged as non-AI. |
| `tests/unit/test_config.py` | `Config` Pydantic model | Valid config accepted. Invalid severity rejected. Invalid confidence threshold (>1.0) rejected. Cadence values correct for each severity. Defaults work without env vars. Env var override works. Session dir expanded (~ → home). |
| `tests/unit/test_session_manager.py` | `SessionManager` | Session saved to SQLite. Session loaded by thread ID. Session list returns all .db files. Session export produces valid JSON. Session delete removes file. Non-existent thread ID → graceful error. |

#### 17.2.2 Unit test conventions

```python
# tests/unit/test_timeline.py
import pytest
from incident_commander.models import TimelineEvent, Alert
from incident_commander.nodes.build_timeline import build_timeline_node, format_timeline
from datetime import datetime

class TestBuildTimeline:
    """Unit tests for timeline construction."""

    def test_multi_source_merge_chronological(self):
        """Events from alert, log, chat, github merge in chronological order."""
        alert = Alert(severity="SEV1", service="payment", summary="down",
                      source="simulated", timestamp=datetime(2026, 7, 12, 14, 3))
        logs = [LogEntry(timestamp=datetime(2026, 7, 12, 14, 7), level="ERROR",
                         message="error rate spike")]
        messages = [ChatMessage(timestamp=datetime(2026, 7, 12, 14, 4),
                                author="jdoe", text="looking into it")]
        prs = [PR(number=4892, title="update pool", author="jdoe",
                  merge_time=datetime(2026, 7, 12, 13, 48))]

        state = IncidentState(alert=alert, input_logs=logs,
                              input_messages=messages, input_prs=prs)
        result = build_timeline_node(state)

        assert len(result.timeline) == 4
        assert result.timeline[0].timestamp < result.timeline[1].timestamp
        assert result.timeline[0].source == "github"  # 13:48 is earliest
        assert result.timeline[-1].source == "log"    # 14:07 is latest

    def test_trust_level_assignment(self):
        """Each source gets the correct trust level."""
        # ... assert trust levels per source

    def test_human_entered_flagged_low(self):
        """Manual events get trust level 'low'."""
        # ...

    def test_empty_sources_timeline_has_only_alert(self):
        """When no logs/messages/PRs, timeline has only the alert event."""
        # ...

    def test_deploy_correlation_marker(self):
        """Events within 30 min of alert get deploy_correlation=True."""
        # ...

    def test_timeline_pagination_500_events(self):
        """500+ events paginate at 50 per page."""
        # ...
```

### 17.3 Integration tests

#### 17.3.1 Test file map

| File | Scope | Key test cases |
|---|---|---|
| `tests/integration/test_graph_wiring.py` | Full graph with mock LLM + mock retriever | All nodes execute in order. State transitions correct. Entry point is `receive_alert`. Terminal node is `cost_report`. Cycle: draft → interrupt → produce → draft works. |
| `tests/integration/test_interrupt_approval.py` | Stakeholder update interrupt flow | Interrupt blocks. Approve → `produce_output` called. Reject → cycles back to `draft_update`. Edit → modified update approved. Resolve → goes to `suggest_remediation`. |
| `tests/integration/test_interrupt_remediation.py` | Remediation interrupt flow | Suggestion displayed with citation + confidence + dry-run. Accept → goes to `generate_postmortem`. Reject → cycles to `suggest_remediation`. Skip → goes to postmortem. |
| `tests/integration/test_interrupt_postmortem.py` | Postmortem interrupt flow | COE draft displayed with AI labels. Approve → goes to `cost_report`. Edit → sections modified. Regenerate → `generate_postmortem` re-run. |
| `tests/integration/test_cost_tracking_flow.py` | Cost tracking across multiple nodes | Multiple LLM calls → cost aggregated. Per-node breakdown correct. Cost report produced at `cost_report` node. Local model → zero cost. Cloud model → non-zero cost. |
| `tests/integration/test_llm_observability_flow.py` | LLM logging across the graph | Every LLM call logged to JSONL. Log contains: node, model, prompt, response, tokens, latency. Multiple calls → multiple lines. |
| `tests/integration/test_cli_simulate.py` | `incident-commander simulate` command | Runs without credentials. Produces output. SEV1/SEV2/SEV3 cadence correct. `--scenario` loads correct scenario. `--seed` produces reproducible output. |
| `tests/integration/test_cli_run.py` | `incident-commander run` command | Loads alert JSON. Loads log files. Loads message export. Loads GitHub export. `--simulate` flag works. |
| `tests/integration/test_cli_timeline.py` | `incident-commander timeline` command | Loads saved session. Displays timeline. Non-existent thread → graceful error. |
| `tests/integration/test_cli_postmortem.py` | `incident-commander postmortem` command | Loads saved session. Generates postmortem. `--model` override works. Non-existent thread → graceful error. |
| `tests/integration/test_session_persistence.py` | Save + resume session | Session saved to SQLite. Session resumed by thread ID. State preserved across resume. Timeline + updates + remediation preserved. |
| `tests/integration/test_deploy_correlation_flow.py` | Deploy correlation in graph context | PR within 30 min → correlation found. PR outside window → no correlation. Correlation displayed in timeline. Correlation included in postmortem. |
| `tests/integration test_evidence_reranking_flow.py` | Reranking in graph context | 20 evidence items → top 10 returned. Reranked order differs from raw retrieval order. Reranked evidence used in remediation suggestion. |
| `tests/integration/test_pasteable_output_flow.py` | Pasteable output after approval | Incident notes block produced. Comms block produced. Both blocks saved to state. Blocks exportable with session. |
| `tests/integration test_edge_cases.py` | All edge cases from PRD §13 | LLM failure → graceful message. Empty knowledge base → no suggestions. No deploy correlation → stated. All sources unavailable → alert-only timeline. |

#### 17.3.2 Integration test conventions

```python
# tests/integration/test_interrupt_approval.py
import pytest
from incident_commander.graph import build_graph
from incident_commander.models import IncidentState, Alert, StakeholderUpdate
from incident_commander.tools.llm import MockLLMRouter
from incident_commander.tools.rag import InMemoryRetriever
from tests.fixtures import build_simulation_state
from datetime import datetime

class TestInterruptApproval:
    """Integration tests for the stakeholder update approval interrupt."""

    @pytest.fixture
    def graph(self):
        """Build graph with mock LLM and mock retriever."""
        config = load_test_config()
        return build_graph(config, llm_router=MockLLMRouter(), retriever=InMemoryRetriever(...))

    @pytest.fixture
    def initial_state(self):
        """Initial state with a simulated SEV1 alert."""
        return build_simulation_state(severity="SEV1", service="payment-service")

    def test_approve_produces_output(self, graph, initial_state):
        """Approving an update produces pasteable output blocks."""
        # Run graph until first interrupt
        state = graph.invoke(initial_state, until="interrupt_approval")

        # Simulate commander approving
        state = graph.invoke(
            state,
            command=Command(resume="a"),  # approve
        )

        assert state.update_approved is True
        assert len(state.stakeholder_updates) == 1
        assert len(state.pasteable_outputs) == 1
        assert "impact" in state.pasteable_outputs[0]["comms_block"].lower()

    def test_reject_redrafts(self, graph, initial_state):
        """Rejecting an update cycles back to draft_update."""
        state = graph.invoke(initial_state, until="interrupt_approval")

        state = graph.invoke(state, command=Command(resume="r"))  # reject

        # Should be back at draft_update → interrupt_approval with new draft
        state = graph.invoke(state, until="interrupt_approval")
        assert state.current_update_draft is not None
        assert state.current_update_draft.update_number == 1  # still draft #1

    def test_resolve_goes_to_remediation(self, graph, initial_state):
        """Resolving at update interrupt goes to remediation."""
        state = graph.invoke(initial_state, until="interrupt_approval")

        state = graph.invoke(state, command=Command(resume="x"))  # resolve

        # Should proceed to suggest_remediation
        state = graph.invoke(state, until="interrupt_remediation")
        assert state.current_remediation is not None
```

### 17.4 E2E tests

#### 17.4.1 Test file map

| File | Scenario | Mock setup | What it validates |
|---|---|---|---|
| `tests/e2e/test_e2e_sev1_simulation.py` | SEV1 payment-service outage, full lifecycle | Mock LLM (returns pre-written updates/suggestions/PM), simulation mode | Full graph runs start to end. All 3 interrupts triggered. Timeline built. Deploy correlation found. Remediation suggested + dry-run. Postmortem in COE format. Cost report produced. LLM logs written. Pasteable output generated. Session saved. |
| `tests/e2e/test_e2e_sev2_simulation.py` | SEV2 api-gateway degradation | Mock LLM, simulation mode | Same as SEV1 but cadence = 15 min. Verify cadence differences. |
| `tests/e2e/test_e2e_sev3_simulation.py` | SEV3 user-service investigation | Mock LLM, simulation mode | Same but cadence = 30 min. Verify minimal scenario works. |
| `tests/e2e/test_e2e_security_incident.py` | SEV1 security incident (no deploy correlation) | Mock LLM, simulation mode | No deploy correlation found. Remediation from past security incidents. Postmortem includes security-specific action items. |
| `tests/e2e/test_e2e_deploy_correlated.py` | Incident with deploy correlation | Mock LLM, simulation mode | Deploy correlation found. Correlation in timeline. Correlation in postmortem. Remediation suggests rollback. Dry-run simulates rollback. |
| `tests/e2e/test_e2e_zero_credentials.py` | Run with no env vars, no API keys, no config | Mock LLM (local mode), simulation mode | Tool starts, runs, produces output. Zero credentials. Zero API calls. Zero cost. |
| `tests/e2e/test_e2e_session_resume.py` | Start incident, save, resume | Mock LLM, simulation mode | Session saved. Resume loads state. Timeline preserved. Updates preserved. Postmortem generation from resumed session. |
| `tests/e2e/test_e2e_cost_report.py` | Full lifecycle, verify cost report | Mock LLM with known token counts | Cost report has per-node breakdown. Total tokens = sum. Total cost = sum. Models listed. Local model → zero cost. |
| `tests/e2e/test_e2e_llm_observability.py` | Full lifecycle, verify LLM logs | Mock LLM | JSONL file created. Every LLM call logged. Fields: node, model, prompt, response, tokens, latency. Line count = number of LLM calls. |
| `tests/e2e/test_e2e_pasteable_output.py` | Full lifecycle, verify pasteable blocks | Mock LLM | Incident notes block produced at each update. Comms block produced. Both saved to session. Both in export JSON. Markdown valid. |
| `tests/e2e/test_e2e_all_scenarios.py` | Run all 8 pre-built scenarios | Mock LLM | Every scenario runs to completion. Each produces valid output. Different severities → different cadences. |

#### 17.4.2 E2E test conventions

```python
# tests/e2e/test_e2e_sev1_simulation.py
import pytest
from incident_commander.graph import build_graph
from incident_commander.simulation import IncidentSimulator, SCENARIOS
from incident_commander.tools.llm import MockLLMRouter
from incident_commander.tools.rag import InMemoryRetriever
from incident_commander.persistence import SessionManager
from tests.fixtures import MockLLMResponses

class TestE2ESEV1Simulation:
    """End-to-end test: SEV1 payment-service outage, full lifecycle."""

    @pytest.fixture
    def graph_and_state(self):
        """Build a complete simulation environment."""
        sim_data = IncidentSimulator(seed=42).simulate(
            service="payment-service",
            severity="SEV1",
        )

        config = load_test_config(mode="simulate")
        llm = MockLLMRouter(responses=MockLLMResponses.sev1_payment_outage())
        retriever = InMemoryRetriever(
            runbooks=sim_data.runbooks,
            past_incidents=sim_data.past_incidents,
        )

        graph = build_graph(config, llm_router=llm, retriever=retriever)

        initial_state = IncidentState(
            alert=sim_data.alert,
            input_logs=sim_data.logs,
            input_messages=sim_data.messages,
            input_prs=sim_data.prs,
            mode="simulate",
            severity="SEV1",
            service="payment-service",
            thread_id="test-sev1-001",
        )

        return graph, initial_state, config

    def test_full_lifecycle_runs_to_completion(self, graph_and_state):
        """The full graph runs from receive_alert to cost_report."""
        graph, state, config = graph_and_state

        # Run through all interrupts, auto-approving each
        state = graph.invoke(state, until="interrupt_approval")
        state = graph.invoke(state, command=Command(resume="a"))  # approve update

        state = graph.invoke(state, until="interrupt_approval")
        state = graph.invoke(state, command=Command(resume="x"))  # resolve

        state = graph.invoke(state, until="interrupt_remediation")
        state = graph.invoke(state, command=Command(resume="a"))  # accept remediation

        state = graph.invoke(state, until="interrupt_postmortem")
        state = graph.invoke(state, command=Command(resume="a"))  # approve postmortem

        state = graph.invoke(state)  # run to END

        assert state.cost_report is not None
        assert state.postmortem is not None
        assert state.postmortem.approved is True

    def test_timeline_built_from_multiple_sources(self, graph_and_state):
        """Timeline contains events from alert, logs, messages, and GitHub."""
        graph, state, _ = graph_and_state
        state = graph.invoke(state, until="draft_update")

        sources = {e.source for e in state.timeline}
        assert "alert" in sources
        assert "log" in sources
        assert "chat" in sources
        assert "github" in sources

    def test_deploy_correlation_found(self, graph_and_state):
        """Deploy correlation identifies PR merged before alert."""
        graph, state, _ = graph_and_state
        state = graph.invoke(state, until="draft_update")

        assert len(state.deploy_correlations) > 0
        assert state.deploy_correlations[0].minutes_before_alert <= 30

    def test_remediation_has_citation_and_confidence(self, graph_and_state):
        """Remediation suggestion includes citation and confidence score."""
        graph, state, _ = graph_and_state
        state = graph.invoke(state, until="interrupt_remediation")

        rem = state.current_remediation
        assert "Source:" in rem.citation
        assert 0.0 <= rem.confidence <= 1.0
        assert len(rem.dry_run_outcome) > 0

    def test_postmortem_is_coe_format(self, graph_and_state):
        """Postmortem follows Amazon COE format with blameless framing."""
        graph, state, _ = graph_and_state
        state = graph.invoke(state, until="interrupt_postmortem")

        pm = state.postmortem
        assert pm.summary.ai_generated is True
        assert pm.timeline.ai_generated is False  # from session state
        assert pm.root_cause_analysis.ai_generated is True
        assert pm.systemic_contributing_factors.ai_generated is True
        assert len(pm.action_items) > 0
        # Blameless: no individual names in contributing factors
        assert "jdoe" not in pm.systemic_contributing_factors.content.lower()

    def test_cost_report_produced(self, graph_and_state):
        """Cost report has per-node breakdown."""
        graph, state, _ = graph_and_state
        state = graph.invoke(state)  # run to END

        report = state.cost_report
        assert report.total_tokens > 0
        assert len(report.per_node) > 0
        assert report.total_estimated_cost_usd >= 0.0  # 0 for local models

    def test_llm_logs_written(self, graph_and_state, tmp_path):
        """LLM logs are written to JSONL with all fields."""
        graph, state, config = graph_and_state
        config.log_dir = str(tmp_path)

        state = graph.invoke(state)  # run to END

        log_file = tmp_path / "llm_calls.jsonl"
        assert log_file.exists()
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) > 0  # at least one LLM call logged

        import json
        entry = json.loads(lines[0])
        assert "node" in entry
        assert "model" in entry
        assert "prompt" in entry
        assert "response" in entry
        assert "input_tokens" in entry
        assert "output_tokens" in entry
        assert "latency_ms" in entry

    def test_pasteable_output_generated(self, graph_and_state):
        """Pasteable output blocks are generated after approval."""
        graph, state, _ = graph_and_state

        state = graph.invoke(state, until="interrupt_approval")
        state = graph.invoke(state, command=Command(resume="a"))  # approve

        assert len(state.pasteable_outputs) > 0
        output = state.pasteable_outputs[0]
        assert "incident_notes" in output
        assert "comms_block" in output
        assert "##" in output["comms_block"]  # markdown header

    def test_session_saved_and_resumable(self, graph_and_state):
        """Session is saved to SQLite and can be resumed."""
        graph, state, config = graph_and_state
        state = graph.invoke(state, until="interrupt_approval")
        state = graph.invoke(state, command=Command(resume="x"))  # resolve

        # Session should be saved
        session_mgr = SessionManager(config.session_dir)
        sessions = session_mgr.list_sessions()
        assert any(s["thread_id"] == "test-sev1-001" for s in sessions)

        # Resume and generate postmortem
        resumed = session_mgr.load_state("test-sev1-001")
        assert resumed.severity == "SEV1"
        assert len(resumed.timeline) > 0

    def test_zero_credentials(self, tmp_path):
        """Tool runs with zero credentials — no env vars, no API keys."""
        # Clear all env vars
        import os
        for key in list(os.environ.keys()):
            if any(x in key for x in ["SLACK", "PAGERDUTY", "GITHUB", "OPENAI", "ANTHROPIC"]):
                del os.environ[key]

        config = load_test_config(mode="simulate")
        assert config.llm.analysis_model.startswith("ollama/")
        assert config.github_token is None
        assert config.qdrant_url is None

        # Graph should build and run
        graph = build_graph(config, llm_router=MockLLMRouter(), retriever=InMemoryRetriever(...))
        sim_data = IncidentSimulator(seed=42).simulate("test-service", "SEV3")
        state = graph.invoke(IncidentState(
            alert=sim_data.alert, mode="simulate", severity="SEV3",
            service="test-service",
        ))
        assert state is not None
```

### 17.5 Real-data integration testing

This is the closest layer to field testing. Instead of only using pre-built simulation scenarios, we run the tool against **real incident data from public postmortems** — the same public Amazon COEs, Google SRE postmortems, Cloudflare/GitLab/GitHub incident reports parsed in §9.0. We test with multiple LLMs and with LLMs + pre-set rules to understand quality differences.

#### 17.5.1 Real incident data sources

We reuse the same public postmortems from §9.0.1, but instead of parsing them for template structure, we extract the raw incident data to use as test input:

| Source | What we extract | How we use it |
|---|---|---|
| Public postmortem timeline | Alert timestamp, events, resolution time | Feed as `alert.json` + `logs` + `messages` to `incident-commander run` |
| Public postmortem root cause | The known root cause | Compare against our tool's suggested root cause |
| Public postmortem action items | The real action items taken | Compare against our tool's suggested action items |
| Public postmortem stakeholder comms | The real comms sent (if included) | Compare against our tool's drafted stakeholder updates |

#### 17.5.2 Test data preparation

```python
# tests/real_data/prepare_incidents.py
"""
Extracts real incident data from public postmortems and converts it
to our tool's input format (alert.json + logs + messages + github PRs).

Output: tests/real_data/incidents/<name>/
  ├── alert.json          # Alert in our format
  ├── logs.json           # Log entries extracted from postmortem timeline
  ├── messages.json       # Chat messages reconstructed from postmortem
  ├── github.json         # PRs mentioned in postmortem (if any)
  ├── expected_pm.json    # The real postmortem — sections, action items, root cause
  └── meta.json           # Source URL, company, severity, date
"""

import json
from pathlib import Path

# Incidents to prepare (manually curated from public postmortems)
REAL_INCIDENTS = [
    {
        "name": "cloudflare-2023-config-outage",
        "source_url": "https://blog.cloudflare.com/...",
        "company": "Cloudflare",
        "severity": "SEV1",
        "service": "global-edge",
        "description": "Config deployment caused global outage",
        "deploy_correlated": True,
    },
    {
        "name": "gitlab-2017-data-loss",
        "source_url": "https://about.gitlab.com/blog/2017-02-10-gitlab-dot-com-database-incident/",
        "company": "GitLab",
        "severity": "SEV1",
        "service": "production-db",
        "description": "Production database data loss after engineer error",
        "deploy_correlated": False,
    },
    {
        "name": "github-2018-degraded-api",
        "source_url": "https://github.blog/2018-10-30-oct21-incident-report/",
        "company": "GitHub",
        "severity": "SEV1",
        "service": "api",
        "description": "24-hour degraded API performance from network partition",
        "deploy_correlated": False,
    },
    {
        "name": "aws-2023-us-east-1",
        "source_url": "AWS public postmortem (if available)",
        "company": "AWS",
        "severity": "SEV1",
        "service": "us-east-1",
        "description": "Regional service degradation",
        "deploy_correlated": False,
    },
    {
        "name": "google-2019-cloud-outage",
        "source_url": "Google public postmortem",
        "company": "Google",
        "severity": "SEV1",
        "service": "gce",
        "description": "Compute engine outage in multiple zones",
        "deploy_correlated": True,
    },
]
```

#### 17.5.3 Test matrix — multiple LLMs + pre-set rules

We run each real incident through multiple configurations to understand quality differences:

| Configuration | LLM | Rules | Purpose |
|---|---|---|---|
| **A: Local LLM only** | Ollama Qwen 2.5 Coder 7B | None | Baseline — cheapest option, no rules |
| **B: Cloud LLM only** | GPT-4o-mini | None | Cloud baseline — cheap cloud model |
| **C: Strong cloud LLM** | GPT-4o | None | High-quality baseline |
| **D: Claude** | Claude 3.5 Sonnet | None | Different model family |
| **E: Local + rules** | Ollama Qwen 2.5 Coder 7B | Pre-set rules | Does adding rules close the gap with cloud? |
| **F: Cloud + rules** | GPT-4o-mini | Pre-set rules | Does adding rules make cheap cloud good enough? |
| **G: Strong cloud + rules** | GPT-4o | Pre-set rules | Best case — strong model + domain rules |
| **H: Local analysis + cloud PM** | Qwen (analysis) + GPT-4o (postmortem) | None | Cost-optimized routing |
| **I: Local analysis + cloud PM + rules** | Qwen (analysis) + GPT-4o (postmortem) | Pre-set rules | Cost-optimized + rules |

#### 17.5.4 Pre-set rules

"Pre-set rules" are deterministic guardrails that constrain the LLM output without relying on LLM reasoning:

```python
# incident_commander/rules/preset_rules.py
"""
Pre-set rules that constrain LLM output deterministically.
These supplement the LLM — they catch what the LLM might miss.

Rules are applied AFTER the LLM generates output, as a validation/filtering layer.
If the LLM output violates a rule, the output is flagged or regenerated.
"""

class PresetRules:
    """Deterministic rules applied to LLM output."""

    def validate_stakeholder_update(self, update: str) -> tuple[bool, list[str]]:
        """Validate a stakeholder update against pre-set rules."""
        violations = []

        # Rule 1: Must have all 4 consequence-first fields
        required_fields = ["Impact:", "Root cause:", "Action:", "Next update:"]
        for field in required_fields:
            if field not in update:
                violations.append(f"Missing field: {field}")

        # Rule 2: No emojis
        if re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]', update):
            violations.append("Contains emojis — stakeholder updates must be clinical")

        # Rule 3: No casual language
        casual_phrases = ["unfortunately", "we're working hard", "bear with us",
                          "oops", "sorry about that", "our bad"]
        for phrase in casual_phrases:
            if phrase.lower() in update.lower():
                violations.append(f"Casual language detected: '{phrase}'")

        # Rule 4: Impact must be quantified (contains a number)
        impact_section = update.split("Root cause:")[0]
        if not re.search(r'\d+', impact_section):
            violations.append("Impact not quantified — include specific numbers")

        # Rule 5: Next update must be a time
        if not re.search(r'\d{1,2}:\d{2}', update.split("Next update:")[-1]):
            violations.append("Next update time not specified")

        return len(violations) == 0, violations

    def validate_postmortem(self, pm: str, severity: str) -> tuple[bool, list[str]]:
        """Validate a postmortem against pre-set rules."""
        violations = []

        # Rule 1: Must have all required COE sections
        required_sections = ["Summary", "Timeline", "Root Cause",
                            "Systemic Contributing Factors", "Action Items"]
        for section in required_sections:
            if section.lower() not in pm.lower():
                violations.append(f"Missing COE section: {section}")

        # Rule 2: SEV1 must have executive summary + customer impact
        if severity == "SEV1":
            if "executive summary" not in pm.lower() and "summary" not in pm.lower():
                violations.append("SEV1 postmortem missing executive summary")
            if "customer impact" not in pm.lower() and "impact" not in pm.lower():
                violations.append("SEV1 postmortem missing customer impact section")

        # Rule 3: Blameless — no individual names as causes
        blameless_violations = re.findall(
            r'(?:caused by [A-Z][a-z]+|\'s fault|should have [A-Z][a-z]+)', pm
        )
        for v in blameless_violations:
            violations.append(f"Blameless violation: '{v}' — name systems, not people")

        # Rule 4: Every action item must have an owner
        action_section = pm.split("Action Items")[-1] if "Action Items" in pm else ""
        action_lines = [l for l in action_section.split("\n") if l.strip().startswith("-")]
        for line in action_lines:
            if "owner:" not in line.lower() and "owner:" not in line.lower():
                violations.append(f"Action item without owner: '{line.strip()}'")

        # Rule 5: Timeline must have timestamps
        if not re.search(r'\d{1,2}:\d{2}', pm):
            violations.append("Timeline has no timestamps")

        # Rule 6: Must cite timeline events in RCA
        rca_section = ""
        if "Root Cause" in pm:
            rca_section = pm.split("Root Cause")[1].split("Systemic")[0]
        if "see " not in rca_section.lower() and "at " not in rca_section.lower():
            violations.append("RCA does not cite timeline events")

        return len(violations) == 0, violations

    def validate_remediation(self, suggestion: str) -> tuple[bool, list[str]]:
        """Validate a remediation suggestion against pre-set rules."""
        violations = []

        # Rule 1: Must have citation
        if "Source:" not in suggestion and "source:" not in suggestion:
            violations.append("Remediation missing source citation")

        # Rule 2: Must have confidence score
        if not re.search(r'[Cc]onfidence:\s*\d', suggestion):
            violations.append("Remediation missing confidence score")

        # Rule 3: Must not suggest auto-execution
        auto_exec_phrases = ["automatically rollback", "auto-deploy", "execute now",
                            "run this command", "execute the following"]
        for phrase in auto_exec_phrases:
            if phrase.lower() in suggestion.lower():
                violations.append(f"Auto-execution suggestion detected: '{phrase}' — NG1 violation")

        return len(violations) == 0, violations
```

#### 17.5.5 Test execution

```python
# tests/real_data/test_real_incidents.py
"""
Real-data integration tests. Runs real incident data through the tool
with multiple LLM configurations. NOT run in CI (requires LLM API access).
Run manually: pytest tests/real_data/ -m "real_data" --llm-config <config>
"""

import pytest
from pathlib import Path
from incident_commander.graph import build_graph
from incident_commander.config import Config, LLMConfig
from incident_commander.rules.preset_rules import PresetRules

REAL_INCIDENTS_DIR = Path("tests/real_data/incidents")
LLM_CONFIGS = {
    "A_local_only": LLMConfig(analysis_model="ollama/qwen2.5-coder:7b"),
    "B_cloud_cheap": LLMConfig(analysis_model="gpt-4o-mini"),
    "C_cloud_strong": LLMConfig(analysis_model="gpt-4o"),
    "D_claude": LLMConfig(analysis_model="claude-3-5-sonnet"),
    "E_local_rules": LLMConfig(analysis_model="ollama/qwen2.5-coder:7b"),
    "F_cloud_cheap_rules": LLMConfig(analysis_model="gpt-4o-mini"),
    "G_cloud_strong_rules": LLMConfig(analysis_model="gpt-4o"),
    "H_hybrid": LLMConfig(
        analysis_model="ollama/qwen2.5-coder:7b",
        postmortem_model="gpt-4o",
    ),
    "I_hybrid_rules": LLMConfig(
        analysis_model="ollama/qwen2.5-coder:7b",
        postmortem_model="gpt-4o",
    ),
}
RULES_CONFIGS = {"E", "F", "G", "I"}  # configs that use pre-set rules

@pytest.mark.real_data
@pytest.mark.parametrize("llm_config_name", LLM_CONFIGS.keys())
@pytest.mark.parametrize("incident_name", [d.name for d in REAL_INCIDENTS_DIR.iterdir() if d.is_dir()])
def test_real_incident_full_lifecycle(llm_config_name: str, incident_name: str):
    """Run a real incident through the full lifecycle with a given LLM config."""
    incident_dir = REAL_INCIDENTS_DIR / incident_name

    # Load real incident data
    alert = load_json(incident_dir / "alert.json")
    logs = load_json(incident_dir / "logs.json")
    messages = load_json(incident_dir / "messages.json")
    github = load_json(incident_dir / "github.json")
    expected_pm = load_json(incident_dir / "expected_pm.json")
    meta = load_json(incident_dir / "meta.json")

    # Build config
    config = Config(
        mode="run",
        llm=LLM_CONFIGS[llm_config_name],
    )
    use_rules = llm_config_name in RULES_CONFIGS
    rules = PresetRules() if use_rules else None

    # Build and run graph with real LLM
    graph = build_graph(config)
    state = run_graph_with_auto_approve(graph, alert, logs, messages, github)

    # Assert output produced
    assert state.postmortem is not None
    assert state.cost_report is not None

    # Compare against expected (the real postmortem)
    pm = state.postmortem

    # --- Quality comparisons ---

    # 1. Root cause: does our tool's RCA match the known root cause?
    rca_relevance = compute_text_similarity(
        pm.root_cause_analysis.content,
        expected_pm["root_cause"],
    )
    assert rca_relevance > 0.3, f"RCA doesn't match known root cause (similarity: {rca_relevance:.2f})"

    # 2. Action items: overlap with real action items
    our_items = {item.description.lower() for item in pm.action_items}
    real_items = {item.lower() for item in expected_pm["action_items"]}
    action_overlap = len(our_items & real_items) / max(len(real_items), 1)
    assert action_overlap > 0.2, f"Low action item overlap: {action_overlap:.0%}"

    # 3. Timeline: key events captured
    timeline_events = {e.content.lower() for e in state.timeline}
    expected_events = {e.lower() for e in expected_pm["timeline_events"]}
    timeline_coverage = len(timeline_events & expected_events) / max(len(expected_events), 1)
    assert timeline_coverage > 0.5, f"Timeline missing key events: {timeline_coverage:.0%}"

    # 4. Blameless: no individual names
    all_pm_text = pm.model_dump_json()
    for person_name in expected_pm.get("people_involved", []):
        assert person_name.lower() not in pm.systemic_contributing_factors.content.lower(), \
            f"Blameless violation: {person_name} named in systemic factors"

    # 5. Pre-set rules validation (if rules enabled)
    if rules:
        valid, violations = rules.validate_postmortem(pm.model_dump_json(), state.severity)
        assert valid, f"Pre-set rule violations: {violations}"

    # 6. Cost: record for comparison across configs
    record_cost(incident_name, llm_config_name, state.cost_report)


@pytest.mark.real_data
def test_compare_llm_configs():
    """Compare output quality across all LLM configurations.
    Run AFTER all test_real_incident_full_lifecycle tests."""
    results = load_all_results()

    # Compare: root cause accuracy by config
    # Compare: action item overlap by config
    # Compare: timeline coverage by config
    # Compare: cost per session by config
    # Compare: rules vs no-rules improvement
    # Compare: local vs cloud vs hybrid

    generate_comparison_report(results)
```

#### 17.5.6 Comparison metrics

For each incident × LLM config combination, we record:

| Metric | How to measure | What it tells us |
|---|---|---|
| **Root cause accuracy** | Text similarity between our RCA and the known root cause from the real postmortem | Does the LLM correctly identify the root cause? |
| **Action item overlap** | % of real action items our tool also suggests | Does the tool surface the same corrective actions? |
| **Timeline coverage** | % of key events from the real postmortem our tool captures | Does the timeline miss critical events? |
| **Stakeholder update quality** | Pre-set rule compliance score | Does the update meet our format standards? |
| **Postmortem COE compliance** | Pre-set rule compliance score | Does the PM meet COE format + blameless rules? |
| **Blameless compliance** | Manual check: no individual names in systemic factors | Does the LLM blame people or systems? |
| **Cost per session** | Total tokens × model pricing | What does each config cost? |
| **Latency** | Wall-clock time per session | How fast is each config? |
| **Rules impact** | Delta between rules vs no-rules for same LLM | Do pre-set rules improve quality? How much? |

#### 17.5.7 Comparison report

```markdown
## Real-Data Test Results — LLM Configuration Comparison

### Root cause accuracy by config

| Config | LLM | Rules | cloudflare-2023 | gitlab-2017 | github-2018 | aws-2023 | google-2019 | Average |
|---|---|---|---|---|---|---|---|---|
| A | Qwen 7B (local) | No | | | | | | |
| B | GPT-4o-mini | No | | | | | | |
| C | GPT-4o | No | | | | | | |
| D | Claude 3.5 Sonnet | No | | | | | | |
| E | Qwen 7B (local) | Yes | | | | | | |
| F | GPT-4o-mini | Yes | | | | | | |
| G | GPT-4o | Yes | | | | | | |
| H | Qwen + GPT-4o (PM) | No | | | | | | |
| I | Qwen + GPT-4o (PM) | Yes | | | | | | |

### Action item overlap by config
(same table structure)

### Timeline coverage by config
(same table structure)

### Cost per session by config

| Config | LLM | Rules | Avg cost/session | Avg latency |
|---|---|---|---|---|
| A | Qwen 7B (local) | No | $0.00 | |
| B | GPT-4o-mini | No | | |
| C | GPT-4o | No | | |
| D | Claude 3.5 Sonnet | No | | |
| E | Qwen 7B (local) | Yes | $0.00 | |
| F | GPT-4o-mini | Yes | | |
| G | GPT-4o | Yes | | |
| H | Qwen + GPT-4o (PM) | No | | |
| I | Qwen + GPT-4o (PM) | Yes | | |

### Rules impact (delta: rules vs no-rules)

| LLM | Config without rules | Config with rules | Delta in RCA accuracy | Delta in PM compliance | Delta in cost |
|---|---|---|---|---|---|
| Qwen 7B | A | E | | | |
| GPT-4o-mini | B | F | | | |
| GPT-4o | C | G | | | |

### Key findings
- Which LLM produces the best root cause analysis?
- Do pre-set rules close the gap between local and cloud LLMs?
- Is the cost difference justified by quality difference?
- Does hybrid routing (local analysis + cloud PM) give best cost/quality ratio?
- Which incidents are hardest for the tool to get right?
- What does the tool miss that real postmortems catch?

### Recommendations
- Default LLM config for v0.1.0: ...
- Should pre-set rules be enabled by default? ...
- Which LLM for which task? ...
```

#### 17.5.8 Quality criteria for real-data test pass

| Criterion | Target | How to measure |
|---|---|---|
| Root cause accuracy (best config) | >60% text similarity with known root cause | Text similarity score per incident |
| Action item overlap (best config) | >30% overlap with real action items | Set intersection / real items |
| Timeline coverage | >70% of key events from real postmortem | Set intersection / expected events |
| Blameless compliance | 100% — no individual names in systemic factors | Manual check across all incidents |
| Pre-set rules improve local LLM | Rules config (E) RCA accuracy > no-rules config (A) by >10% | Delta comparison |
| Cost transparency | Every config produces cost report | Verify in test |
| COE format compliance (with rules) | 100% of postmortems pass pre-set rules | Rules validation |

#### 17.5.9 Simulation scenario field study

In addition to real-data testing, we also run all 8 pre-built simulation scenarios with real LLMs to validate the simulation mode end-to-end:

| Element | Detail |
|---|---|
| **Scope** | All 8 scenarios from `scenarios.py`, run with real LLMs |
| **LLM configs** | Same 9 configs as §17.5.3 (A through I) |
| **Metrics** | Same as real-data tests (§17.5.6), but without comparison to a real postmortem — instead, compare against the scenario's known root cause and expected events |
| **Documentation** | Results in `docs/field-study.md` alongside real-data results |

#### 17.5.10 Documentation output

All results are documented in `docs/field-study.md`:

1. **Real-data results** — per-incident × per-config table with all metrics
2. **Simulation results** — per-scenario × per-config table
3. **Cross-comparison** — real-data vs simulation (does simulation mode predict real-data performance?)
4. **LLM comparison** — which LLM is best for each task?
5. **Rules impact** — do pre-set rules help? By how much?
6. **Cost analysis** — cost per session for each config
7. **Recommendations** — default config for v0.1.0

### 17.6 Test infrastructure

#### 17.6.1 Mock LLM router

```python
# tests/fixtures.py

class MockLLMResponses:
    """Pre-written LLM responses for deterministic testing."""

    @staticmethod
    def sev1_payment_outage() -> dict[str, str]:
        """Responses for the SEV1 payment outage scenario."""
        return {
            "stakeholder_update": (
                "Impact: 2% of payment attempts failing since 14:03 UTC.\n"
                "Root cause: Suspected DB connection pool exhaustion.\n"
                "Action: Investigating rollback of PR #4892.\n"
                "Next update: 14:10 UTC (5 min)."
            ),
            "remediation": (
                "Action: Rollback PR #4892\n"
                "Citation: Source: incident INC-2025-088\n"
                "Confidence: 0.82\n"
                "Similar incidents: INC-2025-088, INC-2025-061\n"
                "Reasoning: 3 similar incidents resolved by rollback."
            ),
            "dry_run": (
                "Expected outcome: Payment success rate returns to >99% "
                "within 2 minutes of rollback.\n"
                "Time to recovery: ~2 minutes\n"
                "Risk: Minimal — rollback restores known-good state.\n"
                "Confidence: 0.85"
            ),
            "postmortem": (
                "### Summary\n...\n"
                "### Root Cause Analysis\n...\n"
                "### Systemic Contributing Factors\n...\n"
                "### Action Items\n- [ ] Increase pool size — Owner: Platform Team — P0\n"
            ),
        }


class MockLLMRouter:
    """Mock LLM router that returns pre-written responses. Zero API calls."""

    def __init__(self, responses: dict[str, str] | None = None):
        self._responses = responses or {}
        self._call_count = 0

    def generate(self, prompt: str, task: str, model: str) -> tuple[str, LLMInfo]:
        self._call_count += 1
        response = self._responses.get(task, f"Mock response for {task}")
        info = LLMInfo(
            model=model,
            input_tokens=len(prompt) // 4,  # rough estimate
            output_tokens=len(response) // 4,
            latency_ms=10,  # instant
        )
        return response, info
```

#### 17.6.2 pytest configuration

```toml
# pyproject.toml [tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=incident_commander --cov-fail-under=80 --strict-markers"
markers = [
    "unit: unit tests — isolated component tests",
    "integration: integration tests — multi-component with mocks",
    "e2e: end-to-end tests — full lifecycle with simulated data",
    "slow: slow tests (excluded from default run)",
]
```

#### 17.6.3 CI workflow

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: ruff check
      - run: mypy --strict
      - run: pytest --cov=incident_commander --cov-fail-under=80
      - run: pip-audit
```

### 17.7 Test coverage targets

| Module | Coverage target | Rationale |
|---|---|---|
| `models/` | ≥95% | Data models are critical; edge cases must be covered |
| `nodes/` | ≥85% | Core logic; mock LLM for all tests |
| `tools/` | ≥90% | External integrations must be mocked thoroughly |
| `simulation/` | ≥90% | Simulation must be reproducible and correct |
| `persistence/` | ≥85% | Session save/load/export must work reliably |
| `cli.py` | ≥80% | Command parsing and dispatch |
| `graph.py` | ≥85% | Graph wiring is critical; integration tests cover this |
| **Overall** | **≥80%** | Enforced by `--cov-fail-under=80` |

---

## 18. Packaging & build

### 18.1 pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["incident_commander"]

[project]
name = "ai-incident-commander"
version = "0.1.0"
description = "AI incident commander for war rooms, timelines, and postmortems."
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [{ name = "Debashish Ghosal" }]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries",
    "Topic :: System :: Systems Administration",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Typing :: Typed",
]
dependencies = [
    "langchain-core>=0.3.0,<0.4.0",
    "langgraph>=0.2.0,<0.3.0",
    "pydantic>=2.0,<3.0",
    "rich>=13.0,<14.0",
    "typer>=0.12.0,<0.13.0",
]

[project.optional-dependencies]
rag = ["qdrant-client>=1.7.0,<2.0.0"]
openai = ["langchain-openai>=0.2.0,<0.3.0"]
anthropic = ["langchain-anthropic>=0.2.0,<0.3.0"]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.5.0",
    "mypy>=1.10",
    "pip-audit>=2.7",
]

[project.scripts]
incident-commander = "incident_commander.cli:app"

[project.urls]
Homepage = "https://github.com/deghosal-2026/ai-incident-commander"
Repository = "https://github.com/deghosal-2026/ai-incident-commander"
Issues = "https://github.com/deghosal-2026/ai-incident-commander/issues"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "D", "ANN"]

[tool.mypy]
strict = true
python_version = "3.11"
```

### 18.2 .env.example

```bash
# LLM Configuration (optional — simulation mode works without any API key)
LLM_MODEL=ollama/qwen2.5-coder:7b
LLM_BASE_URL=http://localhost:11434/v1
# COMMS_MODEL=gpt-4o-mini          # optional cloud model for stakeholder comms
# POSTMORTEM_MODEL=claude-3-5-sonnet  # optional cloud model for postmortem

# OpenAI (optional)
# OPENAI_API_KEY=sk-...

# Anthropic (optional)
# ANTHROPIC_API_KEY=sk-ant-...

# RAG (optional — simulation uses in-memory demo runbooks)
# QDRANT_URL=http://localhost:6333
# QDRANT_COLLECTION=runbooks

# GitHub (optional — JSON export mode works without token)
# GITHUB_TOKEN=ghp_...
# GITHUB_REPO=owner/repo

# Session storage
SESSION_DIR=~/.incident-commander/sessions
LOG_DIR=~/.incident-commander/logs
```

---

## 19. Threat model implementation summary (T1-T7)

| Threat | PRD ref | SPEC section | Implementation |
|---|---|---|---|
| T1 — AI hallucination | FR-4.3, FR-5.4, FR-4.7, FR-5.2 | §3.3, §14.1 | Interrupt before every output. Confidence threshold. Source citations required. Commander reviews all drafts. |
| T2 — Data leakage to cloud LLM | C8, §14 | §16.1 | Local LLM as default. Cloud models opt-in via config. No data sent to cloud unless user explicitly configures it. |
| T3 — Commander acts on hallucinated suggestion | FR-5.2, FR-5.3, FR-5.7 | §8.1, §8.2, §14.1 | Citation + confidence + dry-run. Human judgment is final. |
| T4 — Production change execution | NG1, FR-5.5 | §1.1, §14.2 | No execution nodes in graph. Dry-run is LLM text prediction, not code execution. Architecture has zero execution capability. |
| T5 — Supply chain | §11.4 | §18.1 | Pinned deps. `pip-audit` in CI. No unpinned ranges. |
| T6 — Session data exposure | §14, FR-10.5 | §12 | SQLite in `~/.incident-commander/sessions/`. No cloud sync. User controls file location. Configurable retention. Exportable as JSON. |
| T7 — Prompt injection via incident data | §15.2 | §14.1 | Human reviews all output. Commander can reject any draft. LLM output is never auto-executed or auto-posted. |

---

## 20. Open questions resolution

| OQ | PRD question | SPEC resolution | Section |
|---|---|---|---|
| OQ-1 | Custom postmortem templates beyond COE? | v0.1.0: COE only. Template is hardcoded in `POSTMORTEM_PROMPT`. v0.2.0: configurable templates via config. | §9.1 |
| OQ-2 | Multiple concurrent incidents? | Resolved: v0.1.0 single incident per session. Each session has its own thread ID and SQLite DB. No shared state. | §15 |
| OQ-3 | Multiple audiences for stakeholder updates? | Resolved: v0.1.0 single audience. Single `StakeholderUpdate` format. v0.2.0: audience-specific templates. | §7.1 |
| OQ-4 | incident.io integration? | v0.1.0: alert JSON only. No platform integrations. v0.2.0. | — |
| OQ-5 | "Lessons learned" section in postmortem? | v0.1.0: action items + systemic contributing factors only. "Lessons learned" is human-written — too subjective for AI. | §9.1 |
| OQ-6 | Default LLM routing strategy? | Resolved: local for analysis + comms (default), cloud for postmortem (opt-in). Documented in `docs/llm-strategy.md`. | §16.1 |
| OQ-7 | Pre-built scenario library extensible? | v0.1.0: fixed library in `scenarios.py`. v0.2.0: user-defined scenarios via config file. | §4.2 |
| OQ-8 | Timeline export as CSV/JSON? | v0.1.0: markdown display + JSON session export (via `sessions export`). CSV export in v0.2.0. | §12.2 |

---

## 21. Public API surface (v0.1.0)

```python
# incident_commander/__init__.py

from incident_commander.config import Config, LLMConfig
from incident_commander.models import (
    # Core models (§2)
    Alert,
    TimelineEvent,
    IncidentState,
    DeployCorrelation,
    StakeholderUpdate,
    RemediationSuggestion,
    Postmortem,
    PostmortemSection,
    ActionItem,
    CostReport,
    NodeCost,
    # Input models (§13.11.5)
    ChatMessage,
    LogEntry,
    GitHubPR,
    Runbook,
    IncidentMeta,
    IncidentInput,
    # Output models (§13.11.5)
    IncidentResult,
    SessionMeta,
    LLMCall,
)
from incident_commander.graph import build_graph
from incident_commander.simulation import IncidentSimulator, SCENARIOS
from incident_commander.api import run_incident, run_simulation
from incident_commander.schema import SCHEMAS, export_schemas, validate_input

__version__ = "0.1.0"
__all__ = [
    # Config
    "Config",
    "LLMConfig",
    # Core models
    "Alert",
    "TimelineEvent",
    "IncidentState",
    "DeployCorrelation",
    "StakeholderUpdate",
    "RemediationSuggestion",
    "Postmortem",
    "PostmortemSection",
    "ActionItem",
    "CostReport",
    "NodeCost",
    # Input models
    "ChatMessage",
    "LogEntry",
    "GitHubPR",
    "Runbook",
    "IncidentMeta",
    "IncidentInput",
    # Output models
    "IncidentResult",
    "SessionMeta",
    "LLMCall",
    # Functions
    "build_graph",
    "run_incident",
    "run_simulation",
    # Schema
    "SCHEMAS",
    "export_schemas",
    "validate_input",
    # Simulation
    "IncidentSimulator",
    "SCENARIOS",
]
```

---

## 22. Sign-off

| Role | Name | Date | Status |
|---|---|---|---|
| Engineer | Debashish Ghosal | 2026-07-12 | **Approved** ✅ |
