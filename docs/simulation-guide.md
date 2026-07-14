# Simulation Guide

ai-incident-commander ships with a built-in `IncidentSimulator` and 8
pre-built incident scenarios. This lets you run the full incident-response
graph end-to-end without real input data — ideal for demos, testing, and CI.

This document covers how to run simulated incidents (CLI and Python API),
all 8 scenarios with expected correlations, custom scenario creation, seed
reproducibility, and auto-approve mode.

All details are derived from:
- `src/incident_commander/simulation/scenarios.py` — scenario definitions
- `src/incident_commander/simulation/simulator.py` — `IncidentSimulator` API
- `src/incident_commander/api.py` — `run_simulation()` entry point
- `src/incident_commander/cli.py` — `simulate` CLI command

---

## How to Run Simulated Incidents

### CLI

The `simulate` command runs a simulated incident through the full graph:

```bash
incident-commander simulate [OPTIONS]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--service` | `payment-service` | Service name (used when no `--scenario`) |
| `--severity` | `SEV1` | Severity tier: `SEV1`, `SEV2`, or `SEV3` |
| `--scenario` | `None` | Scenario name from the built-in `SCENARIOS` dict |
| `--seed` | `42` | Random seed for reproducibility |
| `--output-dir` | `None` | Output directory for markdown files |
| `--auto-approve` | `False` | Skip all human-in-the-loop approval gates |

**Examples:**

```bash
# Run a default SEV1 payment-service simulation with auto-approve
incident-commander simulate --auto-approve

# Run a specific scenario
incident-commander simulate --scenario db-connection-pool --auto-approve

# Run with output written to disk
incident-commander simulate --scenario bad-deploy --output-dir ./out --auto-approve

# Run without auto-approve (requires human at each gate — run mode)
incident-commander simulate --scenario cert-expiry --severity SEV1

# Run with a custom seed for a different variation
incident-commander simulate --scenario memory-leak --seed 123 --auto-approve
```

When `--auto-approve` is passed, the config mode is set to `"simulate"`,
which bypasses all three human-in-the-loop interrupt gates (stakeholder
update, remediation review, postmortem review) and auto-approves each draft.
Without `--auto-approve`, the config mode is `"run"` and the graph pauses at
each gate.

### Python API

Use `run_simulation()` from `src/incident_commander/api.py`:

```python
from incident_commander.api import run_simulation

# Default: SEV1 payment-service, seed=42, auto-approve off
result = run_simulation()

# Named scenario
result = run_simulation(scenario="db-connection-pool", auto_approve=True)

# Procedural generation with custom service/severity
result = run_simulation(service="auth-service", severity="SEV2", seed=99)

# Write markdown output to a directory
result = run_simulation(
    scenario="bad-deploy",
    auto_approve=True,
    output_dir="./incident-output",
)
```

**`run_simulation()` signature:**

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

**Return value:** An `IncidentResult` containing `thread_id`, `timeline`,
`stakeholder_updates`, `remediation_suggestions`, `deploy_correlations`,
`postmortem`, `cost_report`, and `session_dir`.

**Two simulation paths:**
1. **Named scenario** (`scenario` is set): Loads a pre-built scenario via
   `load_scenario(name, seed)` — deterministic script with defined
   parameters.
2. **Procedural generation** (`scenario` is `None`): Uses
   `IncidentSimulator(seed)` to synthesize data from `service` and
   `severity` with defaults (`num_logs=15`, `num_messages=8`, `num_prs=3`,
   `deploy_correlated=True`).

### Direct simulator usage

For lower-level control, use `IncidentSimulator` directly:

```python
from incident_commander.simulation.simulator import IncidentSimulator

sim = IncidentSimulator(seed=42)
incident_input = sim.simulate(
    service="payment-service",
    severity="SEV1",
    num_logs=20,
    num_messages=12,
    num_prs=2,
    deploy_correlated=True,
)

# incident_input.alert, .logs, .messages, .github, .runbooks, .meta
```

Then pass the data to `run_incident()`:

```python
from incident_commander.api import run_incident

result = run_incident(
    alert=incident_input.alert,
    logs=incident_input.logs,
    messages=incident_input.messages,
    github=incident_input.github,
    runbooks=incident_input.runbooks,
    auto_approve=True,
)
```

---

## The 8 Pre-Built Scenarios

All scenarios are defined in `SCENARIOS` dict in
`src/incident_commander/simulation/scenarios.py`. Each is a `ScenarioConfig`
with a unique `name`, `service`, `severity`, data volume parameters, a
machine-readable `root_cause` label, a `deploy_correlated` flag, and a list
of `expected_runbook_matches` (runbook IDs the analysis engine should match).

### Scenario 1: `db-connection-pool`

| Field | Value |
|-------|-------|
| **Description** | DB connection pool exhaustion causing payment failures |
| **Service** | `payment-service` |
| **Severity** | `SEV1` |
| **Logs** | 20 |
| **Messages** | 12 |
| **PRs** | 2 |
| **Root cause** | `db_connection_pool_exhaustion` |
| **Deploy correlated** | Yes — a recent deploy caused the incident |
| **Expected runbook matches** | `rb-001` (DB Connection Pool Exhaustion), `rb-002` (Standard Rollback Procedure) |
| **Expected deploy correlation** | PRs merged 5-60 min before the alert; strong correlation expected |

**Symptoms:** Logs transition from INFO (health checks passing) to WARN
(connection pool warnings) to ERROR (pool exhausted, timeouts, HTTP 500s).
Chat messages trace discovery → investigation → rollback → recovery. The two
PRs are merged before the alert, making the deploy the suspected trigger.

### Scenario 2: `bad-deploy`

| Field | Value |
|-------|-------|
| **Description** | Misconfigured route in API gateway from bad deploy |
| **Service** | `api-gateway` |
| **Severity** | `SEV2` |
| **Logs** | 15 |
| **Messages** | 8 |
| **PRs** | 1 |
| **Root cause** | `misconfigured_route` |
| **Deploy correlated** | Yes |
| **Expected runbook matches** | `rb-002` (Standard Rollback Procedure) |
| **Expected deploy correlation** | Single PR merged before alert; strong correlation |

**Symptoms:** API gateway logs show route resolution failures and elevated
latency. The single PR (likely a config/route change) is the deploy
correlation. The rollback runbook (`rb-002`) is the expected match since
this is a deploy-caused issue on a service without a specific runbook.

### Scenario 3: `memory-leak`

| Field | Value |
|-------|-------|
| **Description** | Gradual memory growth causing OOM kills in auth service |
| **Service** | `auth-service` |
| **Severity** | `SEV2` |
| **Logs** | 10 |
| **Messages** | 5 |
| **PRs** | 1 |
| **Root cause** | `memory_leak` |
| **Deploy correlated** | No — not caused by a deploy |
| **Expected runbook matches** | `rb-006` (Memory Leak Investigation) |
| **Expected deploy correlation** | PR is merged AFTER the alert (fix PR, not cause) |

**Symptoms:** Logs show gradual memory increase warnings culminating in OOM
kills. The PR is generated as a post-incident fix (merged after the alert),
so deploy correlation should NOT flag it as the cause. The memory leak
runbook (`rb-006`) should match via keyword overlap (memory, leak, OOM).

### Scenario 4: `cert-expiry`

| Field | Value |
|-------|-------|
| **Description** | TLS certificate expired on API gateway |
| **Service** | `api-gateway` |
| **Severity** | `SEV1` |
| **Logs** | 12 |
| **Messages** | 8 |
| **PRs** | 0 |
| **Root cause** | `cert_expired` |
| **Deploy correlated** | No — infrastructure issue, no deploy involved |
| **Expected runbook matches** | `rb-003` (TLS Certificate Renewal) |
| **Expected deploy correlation** | None — no PRs generated |

**Symptoms:** Logs show TLS handshake failures and SSL errors. No PRs are
generated, so there is no deploy correlation. The cert renewal runbook
(`rb-003`) should match via keywords (tls, cert, certificate, expiry, ssl).

### Scenario 5: `dependency-outage`

| Field | Value |
|-------|-------|
| **Description** | Third-party payment API is down |
| **Service** | `payment-service` |
| **Severity** | `SEV1` |
| **Logs** | 18 |
| **Messages** | 10 |
| **PRs** | 0 |
| **Root cause** | `third_party_down` |
| **Deploy correlated** | No — external dependency failure |
| **Expected runbook matches** | None (`[]`) |
| **Expected deploy correlation** | None — no PRs generated |

**Symptoms:** Logs show timeouts connecting to upstream and HTTP 500s from
the payment processor. No PRs and no specific runbook — this is an external
dependency outage that requires manual investigation. Tests whether the
system correctly identifies the absence of a deploy correlation and surfaces
"no relevant runbook" gracefully.

### Scenario 6: `config-drift`

| Field | Value |
|-------|-------|
| **Description** | Stale configuration in web frontend |
| **Service** | `web-frontend` |
| **Severity** | `SEV3` |
| **Logs** | 6 |
| **Messages** | 3 |
| **PRs** | 1 |
| **Root cause** | `stale_config` |
| **Deploy correlated** | No |
| **Expected runbook matches** | None (`[]`) |
| **Expected deploy correlation** | PR merged after alert (fix, not cause) |

**Symptoms:** Minor degradation — elevated error rate and latency warnings.
This is a low-severity scenario with minimal data volume. Tests the system's
behavior on SEV3 incidents where less data is available and fewer
stakeholder updates are needed (cadence: 30 min for SEV3).

### Scenario 7: `cache-invalidation`

| Field | Value |
|-------|-------|
| **Description** | Stale cache returns incorrect product data |
| **Service** | `product-catalog` |
| **Severity** | `SEV2` |
| **Logs** | 10 |
| **Messages** | 6 |
| **PRs** | 0 |
| **Root cause** | `stale_cache` |
| **Deploy correlated** | No |
| **Expected runbook matches** | `rb-004` (Cache Invalidation) |
| **Expected deploy correlation** | None — no PRs generated |

**Symptoms:** Logs show cache miss cascades and stale data warnings. The
cache invalidation runbook (`rb-004`) should match via keywords (cache,
redis, invalidation, stale, TTL).

### Scenario 8: `rate-limit-hit`

| Field | Value |
|-------|-------|
| **Description** | Upstream rate limit exceeded causing degraded search |
| **Service** | `search-service` |
| **Severity** | `SEV3` |
| **Logs** | 8 |
| **Messages** | 4 |
| **PRs** | 0 |
| **Root cause** | `rate_limit_exceeded` |
| **Deploy correlated** | No |
| **Expected runbook matches** | `rb-005` (Rate Limit Negotiation) |
| **Expected deploy correlation** | None — no PRs generated |

**Symptoms:** Logs show HTTP 429 responses and rate limit exceeded errors.
The rate limit negotiation runbook (`rb-005`) should match via keywords
(rate, limit, 429, throttle, backoff).

### Scenario quick-reference table

| Scenario | Service | Severity | Deploy? | Expected runbooks |
|----------|---------|----------|---------|-------------------|
| `db-connection-pool` | payment-service | SEV1 | Yes | `rb-001`, `rb-002` |
| `bad-deploy` | api-gateway | SEV2 | Yes | `rb-002` |
| `memory-leak` | auth-service | SEV2 | No | `rb-006` |
| `cert-expiry` | api-gateway | SEV1 | No | `rb-003` |
| `dependency-outage` | payment-service | SEV1 | No | (none) |
| `config-drift` | web-frontend | SEV3 | No | (none) |
| `cache-invalidation` | product-catalog | SEV2 | No | `rb-004` |
| `rate-limit-hit` | search-service | SEV3 | No | `rb-005` |

### Runbook reference (demo runbooks)

The simulator loads `DEMO_RUNBOOKS` from
`src/incident_commander/simulation/demo_runbooks.py`:

| ID | Title | Service | Keywords |
|----|-------|---------|----------|
| `rb-001` | DB Connection Pool Exhaustion | payment-service | db, connection, pool, exhaustion, timeout, postgres |
| `rb-002` | Standard Rollback Procedure | `*` (wildcard) | rollback, deploy, revert, pr, production |
| `rb-003` | TLS Certificate Renewal | api-gateway | tls, cert, certificate, expiry, ssl, ingress |
| `rb-004` | Cache Invalidation | product-catalog | cache, redis, invalidation, stale, ttl |
| `rb-005` | Rate Limit Negotiation | search-service | rate, limit, 429, throttle, backoff |
| `rb-006` | Memory Leak Investigation | image-processor | memory, leak, oom, heap, pod, container |

---

## How to Create Custom Scenarios

### Option 1: Add to the `SCENARIOS` dict

Add a new `ScenarioConfig` entry to `SCENARIOS` in
`src/incident_commander/simulation/scenarios.py`:

```python
from incident_commander.simulation.scenarios import SCENARIOS, ScenarioConfig

SCENARIOS["my-custom-incident"] = ScenarioConfig(
    name="my-custom-incident",
    description="Custom incident for my service",
    service="order-service",
    severity="SEV2",
    num_logs=12,
    num_messages=6,
    num_prs=1,
    root_cause="custom_root_cause",
    deploy_correlated=True,
    expected_runbook_matches=["rb-002"],
)
```

Then load it:

```python
from incident_commander.simulation.scenarios import load_scenario

incident_input = load_scenario("my-custom-incident", seed=42)
```

Or via the CLI:

```bash
incident-commander simulate --scenario my-custom-incident --auto-approve
```

### Option 2: Use the simulator directly

For one-off scenarios without modifying the `SCENARIOS` dict, use
`IncidentSimulator.simulate()` with custom parameters:

```python
from incident_commander.simulation.simulator import IncidentSimulator

sim = IncidentSimulator(seed=42)
incident_input = sim.simulate(
    service="order-service",
    severity="SEV2",
    num_logs=25,          # more logs than default
    num_messages=10,
    num_prs=3,            # multiple deploys to correlate
    deploy_correlated=True,  # PRs merged before alert (suspected cause)
)

# Pass to run_incident
from incident_commander.api import run_incident

result = run_incident(
    alert=incident_input.alert,
    logs=incident_input.logs,
    messages=incident_input.messages,
    github=incident_input.github,
    runbooks=incident_input.runbooks,
    auto_approve=True,
)
```

### ScenarioConfig field reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Unique scenario key — must match the dict key in `SCENARIOS` |
| `description` | `str` | (required) | Human-readable summary |
| `service` | `str` | (required) | Affected service name |
| `severity` | `Literal["SEV1","SEV2","SEV3"]` | (required) | Severity tier |
| `num_logs` | `int` | `15` | Number of log entries to generate |
| `num_messages` | `int` | `8` | Number of chat messages to generate |
| `num_prs` | `int` | `3` | Number of GitHub PRs to generate |
| `root_cause` | `str` | `""` | Machine-readable root cause label for evaluation |
| `deploy_correlated` | `bool` | `False` | `True`: PRs merged before alert (deploy caused incident); `False`: PRs merged after (fix PRs) |
| `expected_runbook_matches` | `list[str]` | `[]` | Runbook IDs the analysis engine is expected to match |

### What the simulator generates

`IncidentSimulator.simulate()` produces a full `IncidentInput` from the
scenario parameters:

- **Alert:** A severity-appropriate summary template chosen at random (e.g.
  "Service is down — all requests failing" for SEV1). Incident ID format:
  `SIM-YYYYMMDD-NNN`.
- **Logs:** Entries transition from INFO (health checks, config reloads) to
  WARN (early symptoms) to ERROR (the failure). Timestamps are backdated
  from the alert time. Error messages are drawn from a pool of realistic
  incident symptoms (pool exhaustion, timeouts, HTTP 500, deadlocks, TLS
  failures, rate limits, cache cascades).
- **Messages:** Chat messages trace the incident arc: discovery ("Anyone
  else seeing errors?") → investigation ("Checking logs now...") → rollback
  ("Rolling back PR to be safe") → recovery ("Error rate dropping after
  rollback"). Authors are randomly chosen from alice/bob/charlie/diana. All
  messages are in `#incidents`.
- **PRs:** When `deploy_correlated=True`, PRs are merged 5-60 minutes before
  the alert (suspected cause). When `False`, PRs are merged 1-30 minutes
  after (fix PRs). PR numbers start at 1000. All PRs are labeled `["deploy"]`.
  Files changed: `src/{service}/main.py`, `src/{service}/config.py`.
- **Runbooks:** The full `DEMO_RUNBOOKS` list (6 runbooks) is attached.
- **Meta:** An `IncidentMeta` envelope with incident ID, service, severity,
  start time (5 min before alert), commander ("sim-commander"), oncall
  roster, and tags (`["simulated", service, severity.lower()]`).

---

## Seed Reproducibility

### How seeding works

`IncidentSimulator.__init__(seed)` creates a `random.Random(seed)` instance
(`simulator.py:41`). All random choices (alert summary selection, log
message selection, author selection, PR merge times, incident ID suffix)
draw from this RNG, making output fully deterministic for a given seed.

```python
sim_a = IncidentSimulator(seed=42)
input_a = sim_a.simulate("payment-service", "SEV1")

sim_b = IncidentSimulator(seed=42)
input_b = sim_b.simulate("payment-service", "SEV1")

# input_a and input_b are identical (same alert summary, same logs,
# same messages, same PR merge times, same incident ID)
```

### Default seed

The default seed is **42** everywhere:
- `load_scenario(name, seed=42)` in `scenarios.py:139`
- `run_simulation(..., seed=42)` in `api.py:83`
- `build_and_run()` uses `IncidentSimulator(seed=42)` when no input is
  provided (`graph.py:320`)
- CLI `--seed 42` default in `cli.py:25`

### Using different seeds

Change the seed to get a different variation of the same scenario (different
alert summary, different log messages, different PR merge times):

```bash
# Seed 42 (default)
incident-commander simulate --scenario db-connection-pool --seed 42 --auto-approve

# Seed 99 — different random choices, same scenario structure
incident-commander simulate --scenario db-connection-pool --seed 99 --auto-approve
```

```python
result_42 = run_simulation(scenario="db-connection-pool", seed=42, auto_approve=True)
result_99 = run_simulation(scenario="db-connection-pool", seed=99, auto_approve=True)
# Different alert summaries and log message selections, same service/severity/volume
```

### Non-deterministic mode

Pass `seed=None` for system-entropy-based non-deterministic generation
(useful for fuzz testing):

```python
sim = IncidentSimulator(seed=None)  # random.Random(None) uses OS entropy
```

### Note on timestamps

Generated timestamps are relative to `datetime.now()` at simulation time
(`simulator.py:195`), so absolute timestamps differ between runs even with
the same seed. The **relative ordering and content** are reproducible, but
the wall-clock times are not. For byte-identical reproducibility, mock
`datetime.now()` in tests.

---

## Auto-Approve Mode

### What it does

The `--auto-approve` flag (CLI) or `auto_approve=True` parameter (Python API)
sets `Config.mode = "simulate"`, which causes all three human-in-the-loop
interrupt gates to auto-approve:

| Gate | Node | Simulate mode behavior |
|------|------|------------------------|
| Stakeholder update | `interrupt_for_approval` | Sets `update_approved = True` |
| Remediation review | `interrupt_for_remediation_review` | Sets `remediation_approved = True`, appends suggestion |
| Postmortem review | `interrupt_for_postmortem_review` | Sets `postmortem_approved = True` |

Additionally, in simulate mode, `produce_output_node` sets `resolved = True`
after the first stakeholder update, so the graph exits the comms loop and
proceeds directly to remediation and postmortem without cycling.

### When to use auto-approve

- **Demos:** Run the full graph end-to-end without pausing
- **Testing / CI:** Get complete `IncidentResult` output for assertions
- **Benchmarking:** Measure full-graph latency and cost without human delay
- **Development:** Quickly iterate on graph changes without manual approval

### When NOT to use auto-approve

- **Production incident response:** Use `mode="run"` (omit `--auto-approve`)
  so a human reviews every draft, suggestion, and postmortem before it
  proceeds. This is the core safety guarantee of the system.

### CLI behavior

```bash
# Auto-approve ON — simulate mode, no pauses
incident-commander simulate --scenario db-connection-pool --auto-approve

# Auto-approve OFF — run mode, pauses at each gate
incident-commander simulate --scenario db-connection-pool
```

The CLI sets `Config(mode="simulate" if auto_approve else "run")` and passes
the flag through to `run_simulation()`, which sets `cfg.mode = "simulate"`
when `auto_approve=True` (`api.py:91-92`).

### Python API behavior

```python
# Auto-approve — graph runs to completion
result = run_simulation(scenario="db-connection-pool", auto_approve=True)

# No auto-approve — graph pauses at interrupt gates
# (requires a LangGraph interrupt handler to resume)
result = run_simulation(scenario="db-connection-pool", auto_approve=False)
```
