# API Reference

Complete reference for the ai-incident-commander Python API, Pydantic models,
configuration, schema registry, and simulation scenarios.

All public symbols are importable directly from the top-level package:

```python
import incident_commander as ic
```

---

## `run_incident()`

Execute the full incident-response graph against real input data.

```python
from incident_commander import run_incident
```

### Signature

```python
def run_incident(
    alert: object,
    logs: object = None,
    messages: object = None,
    github: object = None,
    runbooks: object = None,
    manual_events: object = None,
    config: Config | None = None,
    output_dir: str | None = None,
    auto_approve: bool = False,
    thread_id: str | None = None,
) -> IncidentResult
```

### Parameters

| Parameter        | Type             | Default | Description                                                         |
|------------------|------------------|---------|---------------------------------------------------------------------|
| `alert`          | `Alert \| dict \| str \| Path` | — | Triggering alert (model, dict, or file path) — **required**        |
| `logs`           | `list \| str \| Path \| None`  | `None` | Log entries (list of models/dicts, or directory/file path)        |
| `messages`       | `list \| str \| Path \| None`  | `None` | Chat messages (list of models/dicts, or file path)                 |
| `github`         | `list \| str \| Path \| None`  | `None` | GitHub PRs (list of models/dicts, or file path)                    |
| `runbooks`       | `list \| None`    | `None`  | Runbooks (list of model instances or dicts)                        |
| `manual_events`  | `list[TimelineEvent] \| None`  | `None` | Human-supplied timeline events                                     |
| `config`         | `Config \| None`  | `None`  | Configuration object (defaults to `Config()`)                      |
| `output_dir`     | `str \| None`     | `None`  | Output directory; if set, writes all 10 output files               |
| `auto_approve`   | `bool`            | `False` | Skip all approval gates (sets mode to `"simulate"`)                |
| `thread_id`      | `str \| None`     | `None`  | Session thread ID (auto-generated if not provided)                 |

### Return type

`IncidentResult` — the full session output (see [IncidentResult](#incidentresult)).

### Example

```python
from incident_commander import run_incident

result = run_incident(
    alert={
        "severity": "SEV1",
        "service": "payment-service",
        "summary": "Payment success rate dropped below 50%",
        "source": "datadog-monitor",
        "timestamp": "2026-07-13T14:05:00",
    },
    logs="path/to/logs/",
    messages="path/to/messages.json",
    github="path/to/github.json",
    output_dir="./output",
    auto_approve=True,
)

print(f"Thread: {result.thread_id}")
print(f"Timeline events: {len(result.timeline)}")
print(f"Updates: {len(result.stakeholder_updates)}")
```

---

## `run_simulation()`

Run a bundled simulation scenario through the graph for demos and testing. No
real input data required.

```python
from incident_commander import run_simulation
```

### Signature

```python
def run_simulation(
    service: str = "payment-service",
    severity: str = "SEV1",
    scenario: str | None = None,
    seed: int = 42,
    config: Config | None = None,
    output_dir: str | None = None,
    auto_approve: bool = False,
) -> IncidentResult
```

### Parameters

| Parameter      | Type             | Default              | Description                                              |
|----------------|------------------|----------------------|----------------------------------------------------------|
| `service`      | `str`            | `"payment-service"`  | Service name (used when `scenario` is `None`)            |
| `severity`     | `str`            | `"SEV1"`             | Severity (used when `scenario` is `None`)                |
| `scenario`     | `str \| None`    | `None`               | Named scenario from `SCENARIOS` (overrides service/sev)  |
| `seed`         | `int`            | `42`                 | Random seed for reproducibility                           |
| `config`       | `Config \| None` | `None`               | Configuration object                                     |
| `output_dir`   | `str \| None`    | `None`               | Output directory; if set, writes all 10 output files     |
| `auto_approve` | `bool`           | `False`              | Skip all approval gates                                  |

### Return type

`IncidentResult`

### Example

```python
from incident_commander import run_simulation

# Named scenario
result = run_simulation(
    scenario="db-connection-pool",
    output_dir="./output",
    auto_approve=True,
)

# Procedural generation
result = run_simulation(
    service="api-gateway",
    severity="SEV2",
    seed=123,
    output_dir="./output",
)
```

---

## Pydantic Models

### `Alert`

The triggering alert for an incident session.

| Field         | Type                                      | Required | Default    | Description                            |
|---------------|-------------------------------------------|----------|------------|----------------------------------------|
| `severity`    | `Literal["SEV1", "SEV2", "SEV3"]`        | Yes      | —          | Alert severity                         |
| `service`     | `str`                                     | Yes      | —          | Affected service                       |
| `summary`     | `str`                                     | Yes      | —          | Short alert summary                    |
| `source`      | `str`                                     | No       | `"manual"` | Originating system                     |
| `timestamp`   | `datetime`                                | Yes      | —          | Alert trigger time                     |
| `incident_id` | `str`                                     | No       | `""`       | Incident ID                            |
| `metadata`    | `dict[str, Any]`                         | No       | `{}`       | Original payload for traceability      |

### `ChatMessage`

A chat message from Slack, Teams, or other chat export.

| Field       | Type             | Required | Default | Description                              |
|-------------|------------------|----------|---------|------------------------------------------|
| `timestamp` | `datetime`       | Yes      | —       | Message timestamp                        |
| `author`    | `str`            | Yes      | —       | Message author                           |
| `text`      | `str`            | Yes      | —       | Message content                          |
| `channel`   | `str`            | No       | `""`    | Channel name                             |
| `thread_ts` | `str \| None`   | No       | `null`  | Slack thread timestamp for reply grouping|

### `LogEntry`

A single parsed log entry from application or infrastructure logs.

| Field       | Type                                                                    | Required | Default | Description                         |
|-------------|-------------------------------------------------------------------------|----------|---------|-------------------------------------|
| `timestamp` | `datetime`                                                              | Yes      | —       | Log entry timestamp                 |
| `level`     | `Literal["DEBUG","INFO","WARN","ERROR","FATAL","TRACE"]`              | Yes      | —       | Log severity level                  |
| `message`   | `str`                                                                   | Yes      | —       | Log message                         |
| `source`    | `str`                                                                   | No       | `""`    | Entry origin                        |
| `metadata`  | `dict[str, Any]`                                                       | No       | `{}`    | Structured fields (e.g. `trace_id`) |

### `GitHubPR`

A GitHub pull request used for deploy correlation analysis.

| Field          | Type           | Required | Default  | Description                              |
|----------------|----------------|----------|----------|------------------------------------------|
| `number`       | `int`          | Yes      | —        | PR number                                |
| `title`        | `str`          | Yes      | —        | PR title                                 |
| `author`       | `str`          | Yes      | —        | PR author                                |
| `merge_time`   | `datetime`     | Yes      | —        | Merge timestamp                          |
| `files_changed`| `list[str]`   | No       | `[]`     | File paths modified                      |
| `labels`       | `list[str]`   | No       | `[]`     | GitHub labels                            |
| `base_branch`  | `str`          | No       | `"main"` | Target branch                            |

### `Runbook`

A runbook for incident response, indexed by keywords for RAG retrieval.

| Field      | Type        | Required | Default | Description                              |
|------------|-------------|----------|---------|------------------------------------------|
| `id`       | `str`       | No       | `""`    | Unique runbook identifier                |
| `title`    | `str`       | Yes      | —       | Runbook title                            |
| `path`     | `str`       | No       | `""`    | File path or URL                         |
| `content`  | `str`       | Yes      | —       | Runbook content                          |
| `keywords` | `list[str]` | No       | `[]`    | Keywords for RAG indexing                |
| `service`  | `str`       | No       | `""`    | Service this applies to (empty = all)    |

### `IncidentMeta`

Incident metadata from `meta.json`.

| Field          | Type                                      | Required | Default | Description                              |
|----------------|-------------------------------------------|----------|---------|------------------------------------------|
| `incident_id`  | `str`                                     | Yes      | —       | Unique incident identifier               |
| `service`      | `str`                                     | Yes      | —       | Affected service                         |
| `severity`     | `Literal["SEV1", "SEV2", "SEV3"]`        | Yes      | —       | Incident severity                        |
| `start_time`   | `datetime`                                | Yes      | —       | Incident start timestamp                 |
| `description`  | `str`                                     | No       | `""`    | Free-form description                    |
| `commander`    | `str`                                     | No       | `""`    | Person leading the response              |
| `oncall_roster`| `list[str]`                              | No       | `[]`    | Engineers on call                        |
| `tags`         | `list[str]`                              | No       | `[]`    | Free-form labels                         |

### `IncidentInput`

Aggregate input for `run_incident()` — all data channels in one object. Only
`alert` is required.

| Field            | Type                      | Default     | Description                              |
|------------------|---------------------------|-------------|------------------------------------------|
| `schema_version` | `str`                     | `"0.1.0"`   | Input format version                     |
| `alert`          | `Alert`                   | —           | Triggering alert (**required**)          |
| `logs`           | `list[LogEntry]`         | `[]`        | Log entries                              |
| `messages`       | `list[ChatMessage]`      | `[]`        | Chat history                             |
| `github`         | `list[GitHubPR]`         | `[]`        | Recently merged PRs                      |
| `runbooks`       | `list[Runbook]`          | `[]`        | Runbooks for RAG                         |
| `manual_events`  | `list[TimelineEvent]`    | `[]`        | Human-supplied events                    |
| `meta`           | `IncidentMeta \| None`   | `null`      | Optional metadata from meta.json         |

### `TimelineEvent`

A single event in the incident timeline.

| Field               | Type                                                        | Required | Default | Description                              |
|---------------------|-------------------------------------------------------------|----------|---------|------------------------------------------|
| `timestamp`         | `datetime`                                                  | Yes      | —       | Event timestamp                          |
| `source`            | `Literal["alert","chat","log","github","manual"]`          | Yes      | —       | Originating channel                      |
| `event_type`        | `str`                                                       | Yes      | —       | Free-form label                          |
| `content`           | `str`                                                       | Yes      | —       | Event content                            |
| `trust_level`       | `Literal["high","medium","low"]`                           | Yes      | —       | high=verifiable, low=hearsay/inferred    |
| `deploy_correlation`| `bool`                                                      | No       | `False` | True if suspected deploy trigger         |

### `DeployCorrelation`

A GitHub PR/commit correlated with the incident via time proximity.

| Field                   | Type                            | Required | Default     | Description                              |
|-------------------------|---------------------------------|----------|-------------|------------------------------------------|
| `pr_number`             | `int`                           | Yes      | —           | PR number                                |
| `pr_title`              | `str`                           | Yes      | —           | PR title                                 |
| `author`                | `str`                           | Yes      | —           | PR author                                |
| `merge_time`            | `datetime`                      | Yes      | —           | Merge timestamp                          |
| `files_changed`         | `list[str]`                    | No       | `[]`        | Files modified                           |
| `minutes_before_alert`  | `int`                           | Yes      | —           | Minutes between merge and alert (positive)|
| `correlation_strength`  | `Literal["strong","weak"]`     | No       | `"strong"`  | Correlation strength                     |

### `StakeholderUpdate`

A drafted stakeholder update in consequence-first format.

| Field                   | Type        | Required | Default | Description                              |
|-------------------------|-------------|----------|---------|------------------------------------------|
| `update_number`         | `int`       | Yes      | —       | Sequential, starting at 1                |
| `impact`                | `str`       | Yes      | —       | What's broken and who is affected        |
| `root_cause_hypothesis` | `str`       | Yes      | —       | Best-guess root cause                    |
| `action`                | `str`       | Yes      | —       | What the IC is doing about it            |
| `next_update_time`      | `datetime`  | Yes      | —       | When the next update is due              |
| `confidence`            | `float`     | No       | `1.0`   | 0-1 confidence in hypothesis             |
| `approved`              | `bool`      | No       | `False` | Gated by approval interrupt              |
| `timestamp`             | `datetime`  | Yes      | —       | Update timestamp                         |

### `RemediationSuggestion`

A remediation suggestion with citation and dry-run outcome.

| Field               | Type        | Required | Default | Description                              |
|---------------------|-------------|----------|---------|------------------------------------------|
| `action`            | `str`       | Yes      | —       | Remediation action                       |
| `citation`          | `str`       | Yes      | —       | Runbook or incident reference            |
| `confidence`        | `float`     | Yes      | —       | Confidence score                         |
| `dry_run_outcome`   | `str`       | No       | `""`    | Result of simulating the fix             |
| `similar_incidents` | `list[str]` | No       | `[]`    | Historical incident IDs                  |
| `approved`          | `bool`      | No       | `False` | Approval status                          |

### `PostmortemSection`

A single section of the COE-format postmortem.

| Field          | Type   | Required | Default | Description                                    |
|----------------|--------|----------|---------|------------------------------------------------|
| `title`        | `str`  | Yes      | —       | Section title                                  |
| `content`      | `str`  | Yes      | —       | Section body text                              |
| `ai_generated` | `bool` | No       | `True`  | `False` when human-authored                    |

### `ActionItem`

A corrective action from the postmortem.

| Field             | Type                          | Required | Default | Description                          |
|-------------------|-------------------------------|----------|---------|--------------------------------------|
| `description`     | `str`                         | Yes      | —       | What needs to be done                |
| `suggested_owner` | `str`                         | Yes      | —       | Recommended team or person           |
| `priority`        | `Literal["P0","P1","P2"]`    | No       | `"P1"`  | Urgency level                        |
| `ai_generated`    | `bool`                        | No       | `True`  | `False` when human-authored          |

### `Postmortem`

Amazon COE-format postmortem. See [`coe-format.md`](coe-format.md) for the full
specification.

| Field                                | Type                          | Required | Default | Description                              |
|--------------------------------------|-------------------------------|----------|---------|------------------------------------------|
| `incident_id`                        | `str`                         | Yes      | —       | Incident identifier                      |
| `incident_date`                      | `datetime`                    | Yes      | —       | Alert timestamp                          |
| `severity`                           | `str`                         | Yes      | —       | Incident severity                        |
| `service`                            | `str`                         | Yes      | —       | Affected service                         |
| `summary`                            | `PostmortemSection`           | Yes      | —       | Summary section                          |
| `timeline`                           | `PostmortemSection`           | Yes      | —       | Timeline section                         |
| `root_cause_analysis`                | `PostmortemSection`           | Yes      | —       | RCA section                              |
| `systemic_contributing_factors`      | `PostmortemSection`           | Yes      | —       | Systemic factors section                 |
| `action_items`                       | `list[ActionItem]`           | Yes      | —       | Corrective actions                       |
| `customer_impact`                    | `PostmortemSection \| null`  | No       | `null`  | SEV1/SEV2 only                           |
| `stakeholder_communication_log`      | `PostmortemSection \| null`  | No       | `null`  | SEV1 only                                |
| `regulatory_compliance_impact`       | `PostmortemSection \| null`  | No       | `null`  | SEV1 only                                |
| `resolved_at`                        | `datetime \| null`           | No       | `null`  | Last timeline event timestamp (proxy)    |
| `mttr_minutes`                       | `int \| null`                | No       | `null`  | Minutes from alert to resolution         |
| `approved`                           | `bool`                        | No       | `False` | Human review gate                        |

### `NodeCost`

Cost breakdown for a single agent node (one LLM call).

| Field               | Type   | Required | Default | Description                              |
|---------------------|--------|----------|---------|------------------------------------------|
| `node_name`         | `str`  | Yes      | —       | Graph node that made the call            |
| `llm_model`         | `str`  | Yes      | —       | Model ID                                 |
| `input_tokens`      | `int`  | Yes      | —       | Prompt token count                       |
| `output_tokens`     | `int`  | Yes      | —       | Completion token count                   |
| `total_tokens`      | `int`  | Yes      | —       | Sum of input + output                    |
| `estimated_cost_usd`| `float`| Yes      | —       | Estimated cost from pricing lookup       |
| `latency_ms`        | `int`  | Yes      | —       | Wall-clock round-trip time               |

### `CostReport`

Aggregate cost report for an entire incident session.

| Field                      | Type             | Required | Default | Description                              |
|----------------------------|------------------|----------|---------|------------------------------------------|
| `session_id`               | `str`            | Yes      | —       | Session ID                               |
| `total_input_tokens`       | `int`            | Yes      | —       | Total input tokens                       |
| `total_output_tokens`      | `int`            | Yes      | —       | Total output tokens                      |
| `total_tokens`             | `int`            | Yes      | —       | Total tokens                             |
| `total_estimated_cost_usd` | `float`          | Yes      | —       | Total estimated cost                     |
| `per_node`                 | `list[NodeCost]`| Yes      | —       | Breakdown by individual LLM calls        |
| `models_used`              | `list[str]`     | Yes      | —       | Distinct model IDs invoked               |

### `IncidentState`

Full state schema for the incident commander LangGraph. This is the single
state object threaded through every graph node. Every field has a sensible
default so `IncidentState()` is valid at any point in the graph lifecycle.

| Field                      | Type                                              | Default     | Description                              |
|----------------------------|---------------------------------------------------|-------------|------------------------------------------|
| `alert`                    | `Alert \| None`                                  | `null`      | Triggering alert                         |
| `severity`                 | `Literal["SEV1","SEV2","SEV3"]`                  | `"SEV3"`    | Mirrored from alert for routing          |
| `service`                  | `str`                                             | `""`        | Mirrored from alert                      |
| `incident_id`              | `str`                                             | `""`        | Mirrored from alert/meta                 |
| `input_logs`               | `list[LogEntry]`                                 | `[]`        | Input log entries                        |
| `input_messages`           | `list[ChatMessage]`                              | `[]`        | Input chat history                       |
| `input_prs`                | `list[GitHubPR]`                                 | `[]`        | Input merged PRs                         |
| `input_manual_events`      | `list[TimelineEvent]`                            | `[]`        | Human-added events                       |
| `timeline`                 | `list[TimelineEvent]`                            | `[]`        | Merged chronological events              |
| `deploy_correlations`      | `list[DeployCorrelation]`                        | `[]`        | Correlated PRs                           |
| `retrieved_runbooks`       | `list[dict]`                                     | `[]`        | Matched runbooks                         |
| `retrieved_incidents`      | `list[dict]`                                     | `[]`        | Past incidents                           |
| `reranked_evidence`        | `list[dict]`                                     | `[]`        | Post-rerank top-k                        |
| `stakeholder_updates`      | `list[StakeholderUpdate]`                        | `[]`        | Sent/approved updates                    |
| `current_update_draft`     | `StakeholderUpdate \| None`                     | `null`      | Pending draft                            |
| `update_approved`          | `bool`                                            | `False`     | Comms gate flag                          |
| `remediation_suggestions`  | `list[RemediationSuggestion]`                    | `[]`        | Remediation suggestions                  |
| `current_remediation`      | `RemediationSuggestion \| None`                 | `null`      | Pending suggestion                       |
| `remediation_approved`     | `bool`                                            | `False`     | Remediation gate flag                    |
| `postmortem`               | `Postmortem \| None`                            | `null`      | Generated postmortem                     |
| `postmortem_approved`      | `bool`                                            | `False`     | Postmortem gate flag                     |
| `cost_report`              | `CostReport \| None`                            | `null`      | Cost report                              |
| `thread_id`                | `str`                                             | `""`        | LangGraph checkpoint key                 |
| `mode`                     | `Literal["simulate","run"]`                     | `"simulate"`| Session mode                             |
| `resolved`                 | `bool`                                            | `False`     | Set True when incident is over           |
| `last_update_time`         | `datetime \| None`                              | `null`      | Most recent sent update                  |
| `next_update_time`         | `datetime \| None`                              | `null`      | Set by cadence timer                     |

### `SessionMeta`

Session metadata written to the output directory.

| Field            | Type                              | Required | Default     | Description                              |
|------------------|-----------------------------------|----------|-------------|------------------------------------------|
| `thread_id`      | `str`                             | Yes      | —           | Session directory name                   |
| `models_used`    | `list[str]`                      | No       | `[]`        | Distinct LLM models invoked              |
| `total_cost_usd` | `float`                           | No       | `0.0`       | Aggregated cost                          |
| `total_tokens`   | `int`                             | No       | `0`         | Total tokens                             |
| `started_at`     | `datetime \| None`               | No       | `null`      | Wall-clock session start                 |
| `ended_at`       | `datetime \| None`               | No       | `null`      | Wall-clock session end                   |
| `mode`           | `Literal["simulate","run"]`      | No       | `"simulate"`| Session mode                             |
| `auto_approved`  | `bool`                            | No       | `False`     | True if auto-approved                    |

### `LLMCall`

A single LLM API call record.

| Field                | Type         | Required | Default | Description                              |
|----------------------|--------------|----------|---------|------------------------------------------|
| `call_id`            | `str`        | Yes      | —       | Unique call identifier                   |
| `timestamp`          | `datetime`   | Yes      | —       | When the call was made                   |
| `node_name`          | `str`        | Yes      | —       | Graph node that made the call            |
| `model`              | `str`        | Yes      | —       | Model ID                                 |
| `input_tokens`       | `int`        | Yes      | —       | Prompt token count                       |
| `output_tokens`      | `int`        | Yes      | —       | Completion token count                   |
| `total_tokens`       | `int`        | Yes      | —       | Sum of input + output                    |
| `estimated_cost_usd` | `float`      | No       | `0.0`   | Estimated cost from pricing lookup       |
| `latency_ms`         | `int`        | Yes      | —       | Wall-clock round-trip time               |
| `prompt_hash`        | `str`        | No       | `""`    | SHA-256 of rendered prompt               |
| `response_truncated` | `bool`       | No       | `False` | True if hit max_tokens                   |
| `error`              | `str \| null`| No      | `null`  | Populated on API failure                 |

---

## `IncidentResult`

The output of an incident session — the serialization boundary between
in-memory graph state and on-disk output.

### Fields

| Field                    | Type                           | Default | Description                              |
|--------------------------|--------------------------------|---------|------------------------------------------|
| `thread_id`              | `str`                          | —       | Session thread ID                        |
| `timeline`               | `list[TimelineEvent]`         | `[]`    | Merged chronological events              |
| `stakeholder_updates`    | `list[StakeholderUpdate]`     | `[]`    | Drafted/approved updates                 |
| `remediation_suggestions`| `list[RemediationSuggestion]` | `[]`    | Remediation suggestions                  |
| `deploy_correlations`    | `list[DeployCorrelation]`     | `[]`    | Correlated PRs                           |
| `postmortem`             | `Postmortem \| None`          | `null`  | COE-format postmortem                    |
| `cost_report`            | `CostReport \| None`          | `null`  | Aggregate cost report                    |
| `session_dir`            | `str`                          | `""`    | Output directory path                    |

### `to_markdown()`

```python
def to_markdown(self) -> dict[str, str]
```

Convert all output to a dict of filename → markdown content. Produces 7
markdown files (the remaining 3 — `llm-calls.jsonl`, `session.json`,
`meta.json` — are written separately by `MarkdownOutputWriter`).

```python
result = run_simulation(output_dir=None)
files = result.to_markdown()
# files == {
#     "incident-summary.md": "# Incident Summary: ...\n",
#     "timeline.md": "- [timestamp] [source] content\n...",
#     "stakeholder-updates.md": "## Update 1\n...",
#     "comms-blocks.md": "# Communication Blocks\n...",
#     "remediation.md": "## Action\n...",
#     "postmortem.md": "# Postmortem: ...\n",
#     "cost-report.md": "# Cost Report: $...\n",
# }
```

### `to_json()`

```python
def to_json(self) -> dict[str, Any]
```

Export as a JSON-serializable dict for programmatic consumption. Returns the
full Pydantic serialization including nested models.

```python
result = run_simulation(output_dir=None)
data = result.to_json()
# data == { "thread_id": "...", "timeline": [...], ... }
import json
json_str = json.dumps(data, indent=2, default=str)
```

---

## `Config` / `LLMConfig`

### `Config`

Top-level configuration for an incident session.

| Field                                | Type                         | Default                  | Description                                          |
|--------------------------------------|------------------------------|--------------------------|------------------------------------------------------|
| `mode`                               | `Literal["simulate","run"]` | `"simulate"`             | `"simulate"` auto-approves; `"run"` requires gates   |
| `llm`                                | `LLMConfig`                  | `LLMConfig()`            | LLM routing configuration                            |
| `cadence`                            | `dict[str, int]`            | `{"SEV1":5,"SEV2":15,"SEV3":30}` | Minutes between stakeholder updates by severity |
| `confidence_threshold`               | `float`                      | `0.7`                    | Min RAG confidence to surface without review (0-1)   |
| `deploy_correlation_window_minutes`  | `int`                        | `30`                     | Look-back window for PR-to-alert correlation (min)   |
| `qdrant_url`                         | `str \| None`               | `null`                   | Qdrant URL for RAG (`None` disables RAG)             |
| `qdrant_collection`                  | `str`                        | `"runbooks"`             | Qdrant collection name                               |
| `github_token`                       | `str \| None`               | `null`                   | GitHub PAT (`None` = unauthenticated, rate-limited)  |
| `session_dir`                        | `str`                        | `"~/.incident-commander/sessions"` | Session storage directory               |
| `log_dir`                            | `str`                        | `"~/.incident-commander/logs"`     | Log directory                            |
| `output_format`                      | `Literal["markdown","json"]`| `"markdown"`             | Output format                                         |

### `LLMConfig`

LLM routing configuration with per-task model overrides.

| Field                  | Type                          | Default                          | Description                              |
|------------------------|-------------------------------|----------------------------------|------------------------------------------|
| `analysis_model`       | `str`                         | `"ollama/qwen2.5-coder:7b"`      | Primary model for root-cause analysis    |
| `analysis_base_url`    | `str`                         | `"http://localhost:11434/v1"`    | Ollama OpenAI-compatible endpoint        |
| `comms_model`          | `str \| None`                | `null`                           | Override for comms (falls back to analysis)|
| `comms_base_url`       | `str \| None`                | `null`                           | Override for comms base URL              |
| `postmortem_model`     | `str \| None`                | `null`                           | Override for postmortem                  |
| `postmortem_base_url`  | `str \| None`                | `null`                           | Override for postmortem base URL         |
| `model_pricing`        | `dict[str, dict[str, float]]`| *(see below)*                   | Per-1M-token USD pricing                 |

Default `model_pricing`:

```python
{
    "ollama/qwen2.5-coder:7b": {"input": 0.0, "output": 0.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
}
```

Unknown models default to free (`0.0`).

### Example

```python
from incident_commander import Config, LLMConfig

config = Config(
    mode="run",
    llm=LLMConfig(
        analysis_model="gpt-4o",
        comms_model="gpt-4o-mini",
        postmortem_model="gpt-4o",
    ),
    confidence_threshold=0.8,
    deploy_correlation_window_minutes=60,
)
```

---

## `SCENARIOS`

A dict of 8 pre-built simulation scenarios for demos and CI testing. Each
scenario is a `ScenarioConfig` with deterministic parameters.

| Key                    | Severity | Service            | Root Cause                    | Deploy Correlated |
|------------------------|----------|--------------------|-------------------------------|-------------------|
| `db-connection-pool`   | SEV1     | payment-service    | db_connection_pool_exhaustion | Yes               |
| `bad-deploy`           | SEV2     | api-gateway        | misconfigured_route           | Yes               |
| `memory-leak`          | SEV2     | auth-service       | memory_leak                   | No                |
| `cert-expiry`          | SEV1     | api-gateway        | cert_expired                  | No                |
| `dependency-outage`    | SEV1     | payment-service    | third_party_down              | No                |
| `config-drift`         | SEV3     | web-frontend       | stale_config                  | No                |
| `cache-invalidation`   | SEV2     | product-catalog    | stale_cache                   | No                |
| `rate-limit-hit`       | SEV3     | search-service     | rate_limit_exceeded           | No                |

### Usage

```python
from incident_commander import SCENARIOS, load_scenario

# List all scenario names
print(list(SCENARIOS.keys()))

# Load a scenario's generated input
incident_input = load_scenario("db-connection-pool", seed=42)

# Run via run_simulation
result = run_simulation(scenario="bad-deploy", output_dir="./output")
```

---

## `SCHEMAS`

A registry mapping 16 kebab-case schema names to Pydantic model classes. Drives
both JSON Schema export and runtime validation.

| Schema name                  | Pydantic model           |
|------------------------------|--------------------------|
| `alert`                      | `Alert`                  |
| `chat-message`               | `ChatMessage`            |
| `log-entry`                  | `LogEntry`               |
| `github-pr`                  | `GitHubPR`               |
| `runbook`                    | `Runbook`                |
| `incident-meta`              | `IncidentMeta`           |
| `incident-input`             | `IncidentInput`          |
| `incident-result`            | `IncidentResult`         |
| `timeline-event`             | `TimelineEvent`          |
| `deploy-correlation`         | `DeployCorrelation`      |
| `stakeholder-update`         | `StakeholderUpdate`      |
| `remediation-suggestion`     | `RemediationSuggestion`  |
| `postmortem`                 | `Postmortem`             |
| `cost-report`                | `CostReport`             |
| `session-meta`               | `SessionMeta`            |
| `llm-call`                   | `LLMCall`                |

---

## `export_schemas()`

Export all 16 JSON Schemas to individual files in an output directory.

```python
def export_schemas(output_dir: str | Path) -> list[Path]
```

Each schema file includes `$id` (`https://schemas.incident-commander.dev/<name>.json`)
and `$schema` (`https://json-schema.org/draft/2020-12/schema`) headers.

### Example

```python
from incident_commander import export_schemas

paths = export_schemas("./schemas")
print(f"Exported {len(paths)} schemas")
# Exported 16 schemas
```

CLI equivalent:

```bash
incident-commander export-schemas --output-dir ./schemas
```

---

## `validate_input()`

Validate a dict against a named schema.

```python
def validate_input(data: dict[str, Any], schema_name: str) -> bool
```

Returns `True` if valid, raises `pydantic.ValidationError` if invalid. Raises
`KeyError` if `schema_name` is not in `SCHEMAS`.

### Example

```python
from incident_commander import validate_input

# Validate an alert
is_valid = validate_input(
    {
        "severity": "SEV1",
        "service": "payment-service",
        "summary": "Payment failures",
        "timestamp": "2026-07-13T14:05:00",
    },
    schema_name="alert",
)
# Returns True

# Validate a log entry
is_valid = validate_input(
    {
        "timestamp": "2026-07-13T14:05:00",
        "level": "ERROR",
        "message": "Connection pool exhausted",
    },
    schema_name="log-entry",
)
# Returns True

# Invalid input raises ValidationError
# validate_input({"severity": "SEV9"}, schema_name="alert")  # raises
```

CLI equivalent (alerts only):

```bash
incident-commander validate --alert path/to/alert.json
```

---

## Public Exports

All symbols available from `incident_commander` (the package `__all__`):

| Symbol                | Type                              |
|-----------------------|-----------------------------------|
| `run_incident`        | function                          |
| `run_simulation`      | function                          |
| `build_graph`         | function                          |
| `Config`              | Pydantic model                    |
| `LLMConfig`           | Pydantic model                    |
| `IncidentState`       | Pydantic model                    |
| `IncidentInput`       | Pydantic model                    |
| `IncidentResult`      | Pydantic model                    |
| `IncidentMeta`        | Pydantic model                    |
| `Alert`               | Pydantic model                    |
| `ChatMessage`         | Pydantic model                    |
| `LogEntry`            | Pydantic model                    |
| `GitHubPR`            | Pydantic model                    |
| `TimelineEvent`       | Pydantic model                    |
| `DeployCorrelation`   | Pydantic model                    |
| `StakeholderUpdate`   | Pydantic model                    |
| `RemediationSuggestion`| Pydantic model                  |
| `Postmortem`          | Pydantic model                    |
| `PostmortemSection`   | Pydantic model                    |
| `ActionItem`          | Pydantic model                    |
| `CostReport`          | Pydantic model                    |
| `NodeCost`            | Pydantic model                    |
| `LLMCall`             | Pydantic model                    |
| `SessionMeta`         | Pydantic model                    |
| `Runbook`             | Pydantic model                    |
| `InMemoryRetriever`   | class                             |
| `SCENARIOS`           | `dict[str, ScenarioConfig]`      |
| `SCHEMAS`             | `dict[str, type[BaseModel]]`     |
| `load_scenario`       | function                          |
| `export_schemas`      | function                          |
| `validate_input`      | function                          |
| `IncidentSimulator`   | class                             |

```python
from incident_commander import (
    run_incident, run_simulation, build_graph,
    Config, LLMConfig,
    IncidentState, IncidentInput, IncidentResult, IncidentMeta,
    Alert, ChatMessage, LogEntry, GitHubPR, TimelineEvent,
    DeployCorrelation, StakeholderUpdate, RemediationSuggestion,
    Postmortem, PostmortemSection, ActionItem,
    CostReport, NodeCost, LLMCall, SessionMeta, Runbook,
    InMemoryRetriever,
    SCENARIOS, SCHEMAS, load_scenario, export_schemas, validate_input,
    IncidentSimulator,
)
```
