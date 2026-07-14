# Contributing to ai-incident-commander

Thanks for your interest in contributing! This document covers how to set up your development environment, run tests, and submit changes.

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/deghosal-2026/ai-incident-commander.git
cd ai-incident-commander
pip install -e ".[dev]"

# Run tests
pytest

# Lint and typecheck
ruff check src/ tests/
mypy --strict src/
```

---

## Project Structure

```
src/incident_commander/
├── api.py              # Public API: run_incident, run_simulation
├── cli.py              # CLI entry point (7 commands)
├── config.py           # Config, LLMConfig Pydantic models
├── graph.py            # LangGraph state graph (14 nodes)
├── llm_router.py       # LLM routing, cost tracking, observability
├── persistence.py      # Session persistence (JSON files)
├── schema.py           # JSON Schema registry, validation, export
├── ingest/             # Input parsers (input_dir, log_parser, notes_parser, normalizer)
├── models/             # Pydantic models (state, input, output)
├── nodes/              # LangGraph node functions
│   ├── timeline.py       # Timeline construction
│   ├── deploy_correlation.py  # GitHub PR correlation
│   ├── rag.py           # Runbook retrieval
│   ├── rerank.py        # Evidence reranking
│   ├── cadence.py       # Severity-based update timing
│   ├── stakeholder.py   # Stakeholder update drafting
│   ├── remediation.py   # Remediation suggestion
│   ├── postmortem.py    # COE-format postmortem generation
│   ├── cost_report.py   # Cost aggregation
│   └── _llm.py          # Module-level LLM router singleton
├── output/             # Output formatters (markdown_writer, formatters, comms_blocks)
└── simulation/         # Incident simulator + 8 scenarios
```

---

## Code Standards

- **Python:** 3.11+
- **ruff:** All checks pass (`ruff check src/ tests/`)
- **mypy:** `--strict` passes (`mypy --strict src/`)
- **Coverage:** ≥80% (`pytest --cov=incident_commander --cov-fail-under=80`)

All public functions need docstrings. Tests should use descriptive names (`test_<unit>_<scenario>`) with one-line docstrings.

---

## Running Tests

```bash
# All tests (excluding real-data which requires a real LLM)
pytest tests/ -v -m "not real_data"

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# E2E tests only
pytest tests/e2e/ -v

# Real-data tests (requires MLX LLM server or OpenCode Zen API key)
export LLM_MODEL=deepseek-v4-flash
export LLM_BASE_URL=https://opencode.ai/zen/v1
export LLM_API_KEY=<your-key>
pytest tests/real_data/ -m real_data -v

# With coverage
pytest --cov=incident_commander --cov-fail-under=80
```

---

## Adding a New Simulation Scenario

1. Add the scenario to `src/incident_commander/simulation/scenarios.py`:

```python
SCENARIOS["my-incident"] = ScenarioConfig(
    service="my-service",
    severity="SEV2",
    deploy_correlated=False,
    num_logs=15,
    num_messages=8,
    num_prs=0,
)
```

2. Add a matching runbook in `src/incident_commander/simulation/demo_runbooks.py`
3. Add tests in `tests/unit/test_simulation.py`

---

## Adding a New LangGraph Node

1. Create the node function in `src/incident_commander/nodes/`:

```python
def my_node(state: IncidentState) -> dict[str, object]:
    """Process state and return updates."""
    return {"result_field": ...}
```

2. Register the node and edges in `src/incident_commander/graph.py`
3. Add integration tests in `tests/integration/`
4. Update `docs/architecture.md` with the new node

---

## Adding a New Input Format

1. Add a parser in `src/incident_commander/ingest/`
2. Wire it into `src/incident_commander/ingest/input_dir.py`
3. Add a JSON Schema in `src/incident_commander/schema.py`
4. Add unit tests in `tests/unit/`

---

## Adding a New Output Format

1. Add a formatter in `src/incident_commander/output/formatters.py`
2. Wire it into `src/incident_commander/output/markdown_writer.py`
3. Add tests in `tests/unit/test_formatters.py`

---

## Submitting Changes

1. Create a feature branch: `git checkout -b feature/my-change`
2. Make your changes
3. Run `make check-all` (lint + typecheck + test + coverage)
4. Push and open a PR

All PRs must:
- Include tests
- Pass `ruff check`, `mypy --strict`, `pytest --cov`
- Preserve safety guardrails (interrupt points, confidence threshold, citation requirements)
- Include AI section labels in postmortem output
- Not contain secrets or local paths

---

## Getting Help

- Open a [GitHub issue](https://github.com/deghosal-2026/ai-incident-commander/issues)
- Check [good first issues](https://github.com/deghosal-2026/ai-incident-commander/labels/good%20first%20issue) for beginner-friendly tasks
