# Input Format

ai-incident-commander accepts incident data through two primary modes: a
structured **input directory** (recommended for complex, multi-source incidents)
and **individual CLI flags** (for quick single-input runs). Both modes feed the
same normalizer pipeline, so the underlying Pydantic models are identical.

---

## Input Directory Structure

When you pass `--input-dir`, the loader (`InputDirLoader`) expects a directory
with the following layout. Only `meta.json` and `alert.json` are required; all
other files and sub-directories are optional.

```
incident-2026-001/
├── meta.json            # required — incident metadata
├── alert.json           # required — triggering alert payload
├── logs/                # optional — log files (.log, .json, .md)
│   ├── app.log
│   ├── infra.json
│   └── captured.md
├── messages.json        # optional — chat/message export
├── github.json          # optional — GitHub PR data
├── runbooks/            # optional — runbook files (.json)
│   ├── rb-001.json
│   └── rb-002.json
└── notes.md             # optional — free-form incident notes
```

Missing optional files are silently replaced with defaults (empty lists or
`None`). Unknown file extensions in `logs/` and `runbooks/` are skipped.

---

## meta.json

Incident metadata that identifies and contextualizes the incident. Maps to the
`IncidentMeta` model.

| Field          | Type                          | Required | Description                                      |
|----------------|-------------------------------|----------|--------------------------------------------------|
| `incident_id`  | `str`                         | Yes      | Unique incident identifier                       |
| `service`      | `str`                         | Yes      | Affected service name                            |
| `severity`     | `"SEV1" \| "SEV2" \| "SEV3"` | Yes      | Incident severity                                |
| `start_time`   | `datetime` (ISO 8601)         | Yes      | Incident start timestamp                         |
| `description`  | `str`                         | No       | Free-form description (default `""`)             |
| `commander`    | `str`                         | No       | Person leading the response (default `""`)       |
| `oncall_roster`| `list[str]`                   | No       | Engineers on call for escalation (default `[]`)  |
| `tags`         | `list[str]`                   | No       | Free-form labels for search/grouping (default `[]`)|

### Example

```json
{
  "incident_id": "INC-2026-001",
  "service": "payment-service",
  "severity": "SEV1",
  "start_time": "2026-07-13T14:00:00",
  "description": "Payment processing failures during peak traffic",
  "commander": "Alice Chen",
  "oncall_roster": ["Bob Smith", "Carol Jones"],
  "tags": ["payments", "sev1", "peak-traffic"]
}
```

---

## alert.json

The triggering alert payload. Maps to the `Alert` model. Field names align with
the PagerDuty Common Event Format (PD-CEF) — `summary` maps to PD-CEF `summary`,
`severity` to `severity`, `source` to `source_component`, and `metadata` preserves
the original payload for traceability.

| Field         | Type                          | Required | Default     | Description                                      |
|---------------|-------------------------------|----------|-------------|--------------------------------------------------|
| `severity`    | `"SEV1" \| "SEV2" \| "SEV3"` | Yes      | —           | Alert severity                                   |
| `service`     | `str`                         | Yes      | —           | Affected service                                 |
| `summary`     | `str`                         | Yes      | —           | Short alert summary (PD-CEF `summary`)           |
| `source`      | `str`                         | No       | `"manual"`  | Originating system (PD-CEF `source_component`)   |
| `timestamp`   | `datetime` (ISO 8601)         | Yes      | —           | Alert trigger time                               |
| `incident_id` | `str`                         | No       | `""`        | Incident ID (populated from meta or auto-generated)|
| `metadata`    | `dict[str, Any]`             | No       | `{}`        | Original payload preserved for traceability      |

### Example

```json
{
  "severity": "SEV1",
  "service": "payment-service",
  "summary": "Payment success rate dropped below 50%",
  "source": "datadog-monitor",
  "timestamp": "2026-07-13T14:05:00",
  "incident_id": "INC-2026-001",
  "metadata": {
    "monitor_id": "mon-98765",
    "threshold": 0.5,
    "window_minutes": 5
  }
}
```

---

## messages.json

A JSON array of chat messages from Slack, Teams, or other chat exports. Maps to
`list[ChatMessage]`.

| Field       | Type                    | Required | Default | Description                                  |
|-------------|-------------------------|----------|---------|----------------------------------------------|
| `timestamp` | `datetime` (ISO 8601)  | Yes      | —       | Message timestamp                            |
| `author`    | `str`                   | Yes      | —       | Message author                               |
| `text`      | `str`                   | Yes      | —       | Message content                              |
| `channel`   | `str`                   | No       | `""`    | Channel name (empty = no channel context)    |
| `thread_ts` | `str \| null`          | No       | `null`  | Slack thread timestamp for reply grouping    |

### Example

```json
[
  {
    "timestamp": "2026-07-13T14:06:00",
    "author": "alice",
    "text": "Seeing a huge spike in payment errors starting ~2:05pm",
    "channel": "#incidents",
    "thread_ts": null
  },
  {
    "timestamp": "2026-07-13T14:08:00",
    "author": "bob",
    "text": "Confirmed — connection pool is exhausted on the primary DB",
    "channel": "#incidents",
    "thread_ts": "14:06"
  }
]
```

---

## github.json

A JSON array of recently merged GitHub pull requests, used for deploy
correlation analysis. Maps to `list[GitHubPR]`.

| Field          | Type                    | Required | Default | Description                              |
|----------------|-------------------------|----------|---------|------------------------------------------|
| `number`       | `int`                   | Yes      | —       | PR number on GitHub                      |
| `title`        | `str`                   | Yes      | —       | PR title                                 |
| `author`       | `str`                   | Yes      | —       | PR author (GitHub username)              |
| `merge_time`   | `datetime` (ISO 8601)  | Yes      | —       | Merge timestamp                          |
| `files_changed`| `list[str]`            | No       | `[]`    | File paths modified by the PR            |
| `labels`       | `list[str]`            | No       | `[]`    | GitHub labels (e.g. `"hotfix"`, `"deploy"`)|
| `base_branch`  | `str`                   | No       | `"main"`| Target branch the PR was merged into     |

### Example

```json
[
  {
    "number": 4521,
    "title": "Increase DB connection pool size",
    "author": "carol",
    "merge_time": "2026-07-13T13:45:00",
    "files_changed": ["config/db-pool.yaml", "src/db/client.py"],
    "labels": ["hotfix", "deploy"],
    "base_branch": "main"
  }
]
```

---

## Log File Formats

The `logs/` sub-directory accepts three file formats, dispatched by extension.
All parsed entries become `LogEntry` objects.

### `LogEntry` fields

| Field       | Type                                              | Required | Default | Description                              |
|-------------|---------------------------------------------------|----------|---------|------------------------------------------|
| `timestamp` | `datetime`                                        | Yes      | —       | Log entry timestamp                      |
| `level`     | `"DEBUG"|"INFO"|"WARN"|"ERROR"|"FATAL"|"TRACE"`  | Yes      | —       | Log severity level                       |
| `message`   | `str`                                             | Yes      | —       | Log message                              |
| `source`    | `str`                                             | No       | `""`    | Entry origin (empty if not captured)     |
| `metadata`  | `dict[str, Any]`                                 | No       | `{}`    | Structured fields (e.g. `trace_id`)      |

### `.log` format

Each line must match the pattern `TIMESTAMP LEVEL SOURCE: MESSAGE`. Accepted
timestamp formats include ISO 8601 (`2026-07-13T14:05:00`), space-separated
(`2026-07-13 14:05:00`), `HH:MM`, and Unix epoch seconds. Slash-separated dates
(`2026/07/13 14:05:00`) are converted to hyphens.

```
2026-07-13T14:05:00 ERROR payment-service: Connection pool exhausted
2026-07-13T14:05:01 WARN payment-service: Retrying request (attempt 1/3)
2026-07-13T14:05:05 FATAL db-client: Pool acquire timeout after 30s
2026-07-13T14:06:00 INFO api-gateway: Health check returning 503
```

### `.json` format

A JSON array of log entry objects. Each object is validated as a `LogEntry`. If
an item lacks a `source` field, the file path is used as the default. Malformed
items are skipped individually so one bad entry doesn't lose all logs.

```json
[
  {
    "timestamp": "2026-07-13T14:05:00",
    "level": "ERROR",
    "message": "Connection pool exhausted",
    "source": "payment-service",
    "metadata": {"trace_id": "abc-123", "pool_size": 10}
  },
  {
    "timestamp": "2026-07-13T14:05:05",
    "level": "FATAL",
    "message": "Pool acquire timeout after 30s",
    "source": "db-client"
  }
]
```

### `.md` format

Markdown files with fenced code blocks. The parser extracts content between
` ``` ` fences and parses each line as a `.log`-format entry. Non-fenced prose
is ignored.

````markdown
# Captured Logs

## Application logs

```log
2026-07-13T14:05:00 ERROR payment-service: Connection pool exhausted
2026-07-13T14:05:05 FATAL db-client: Pool acquire timeout after 30s
```

## Infrastructure logs

```log
2026-07-13T14:06:00 INFO k8s: Pod payment-service-7 restarted
```
````

---

## notes.md

Free-form incident notes parsed into timeline events via `## `-style Markdown
headings. Each `## ` heading becomes a `TimelineEvent` with `source="manual"`
and `trust_level="low"`.

The timestamp is extracted from the heading text or the first line of body
content. Accepted patterns include ISO 8601 (`2026-07-13T14:05:00`) and 24-hour
`HH:MM` (assumes today's date). If no timestamp is found, the current time is
used as a fallback.

The heading text (minus the timestamp) becomes `event_type`, and the body
content becomes `content`.

### Example

```markdown
# Incident Notes — INC-2026-001

## 14:05 — First responder notices spike
Alice spotted the error rate spike on the Datadog dashboard.
Error rate jumped from 0.1% to 52% within 2 minutes.

## 14:10 — IC declared
Bob declared incident commander and opened the incident channel.

## 14:20 — Rollback started
Canary deploy from PR #4521 is suspected. Rollback initiated.
```

This produces three `TimelineEvent` objects at 14:05, 14:10, and 14:20, all with
`source="manual"` and `trust_level="low"`.

---

## runbooks/ Directory

Contains runbook JSON files used for RAG retrieval. Each `.json` file may
contain a single runbook object or an array of runbook objects. Maps to
`list[Runbook]`.

| Field      | Type        | Required | Default | Description                                    |
|------------|-------------|----------|---------|------------------------------------------------|
| `id`       | `str`       | No       | `""`    | Unique runbook identifier                      |
| `title`    | `str`       | Yes      | —       | Runbook title                                  |
| `path`     | `str`       | No       | `""`    | File path or URL                               |
| `content`  | `str`       | Yes      | —       | Runbook content (steps, procedures)            |
| `keywords` | `list[str]` | No       | `[]`    | Keywords for RAG indexing                      |
| `service`  | `str`       | No       | `""`    | Service this runbook applies to (empty = all)  |

### Example (`runbooks/rb-001.json`)

```json
{
  "id": "rb-001",
  "title": "DB Connection Pool Exhaustion",
  "path": "runbooks/db-pool-exhaustion.md",
  "content": "1. Check current pool size: `show pool_status`\n2. Increase pool size in config/db-pool.yaml\n3. Restart affected pods\n4. Monitor error rate for 5 minutes",
  "keywords": ["db", "connection", "pool", "exhausted", "timeout"],
  "service": "payment-service"
}
```

---

## CLI Flags Mode

For simple, single-input runs, you can pass individual files via CLI flags
without creating a full directory structure.

```bash
# Minimal: alert only
incident-commander run --alert alert.json --output-dir ./output

# Alert + logs directory
incident-commander run --alert alert.json --logs ./logs --output-dir ./output

# All channels
incident-commander run \
  --alert alert.json \
  --logs ./logs \
  --messages messages.json \
  --github github.json \
  --output-dir ./output \
  --auto-approve
```

### CLI flags reference

| Flag           | Description                                          |
|----------------|------------------------------------------------------|
| `--alert`      | Path to alert JSON file (required unless `--input-dir`)|
| `--logs`       | Path to logs directory or log file                    |
| `--messages`   | Path to messages JSON file                            |
| `--github`     | Path to GitHub PRs JSON file                          |
| `--input-dir`  | Path to structured input directory (overrides flags)  |
| `--output-dir` | Output directory for generated files                  |
| `--auto-approve`| Skip all approval gates (sets mode to `simulate`)    |

Each flag file is passed through the normalizer, which accepts dicts, model
instances, or file paths. Either `--alert` or `--input-dir` is required.

---

## Python API Mode

For programmatic use, call `run_incident()` directly. All inputs accept
Pydantic model instances, raw dicts, or file path strings — the normalizer
dispatches on type at runtime.

```python
from incident_commander import run_incident, Alert

result = run_incident(
    alert={
        "severity": "SEV1",
        "service": "payment-service",
        "summary": "Payment success rate dropped below 50%",
        "source": "datadog-monitor",
        "timestamp": "2026-07-13T14:05:00",
    },
    logs="path/to/logs/",           # directory or file path
    messages="path/to/messages.json",
    github="path/to/github.json",
    runbooks=[
        {
            "id": "rb-001",
            "title": "DB Connection Pool Exhaustion",
            "content": "1. Check pool size...",
            "keywords": ["db", "pool", "exhausted"],
            "service": "payment-service",
        }
    ],
    manual_events=[
        {
            "timestamp": "2026-07-13T14:10:00",
            "source": "manual",
            "event_type": "IC declared",
            "content": "Bob declared incident commander",
            "trust_level": "low",
        }
    ],
    output_dir="./output",
    auto_approve=True,
)
```

You can also use the `InputDirLoader` directly to load a directory and pass
the resulting `IncidentInput` to `run_incident()`:

```python
from incident_commander.ingest.input_dir import InputDirLoader
from incident_commander import run_incident

loader = InputDirLoader("incident-2026-001/")
incident_input = loader.load()

result = run_incident(
    alert=incident_input.alert,
    logs=incident_input.logs,
    messages=incident_input.messages,
    github=incident_input.github,
    runbooks=incident_input.runbooks,
    manual_events=incident_input.manual_events,
    output_dir="./output",
)
```

---

## JSON Schema Validation

ai-incident-commander ships with a JSON Schema registry covering all input and
output models. Use the `validate` CLI command to check an alert file before
running a full incident session:

```bash
# Validate an alert file against the Alert schema
incident-commander validate --alert path/to/alert.json
```

Output on success:

```
Alert validation: PASSED
```

### Programmatic validation

```python
from incident_commander import validate_input, export_schemas

# Validate any data against a named schema
is_valid = validate_input(
    {"severity": "SEV1", "service": "payment-service", "summary": "...", "timestamp": "2026-07-13T14:05:00"},
    schema_name="alert",
)
# Returns True, or raises pydantic.ValidationError on mismatch

# Export all 16 JSON Schemas to files
paths = export_schemas("./schemas")
```

### Available schemas

The `SCHEMAS` registry contains 16 named schemas:

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

Use `export-schemas` CLI command to write all schemas to a directory:

```bash
incident-commander export-schemas --output-dir ./schemas
```
