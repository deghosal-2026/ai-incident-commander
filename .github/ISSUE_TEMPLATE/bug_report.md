---
name: Bug Report
about: Report a bug to help us improve
title: "[BUG] "
labels: bug
assignees: ''
---

## Bug Description
A clear description of the bug.

## Steps to Reproduce
1. Run `incident-commander ...`
2. See output...
3. Error appears...

## Expected Behavior
What should have happened.

## Actual Behavior
What actually happened.

## Environment
- **incident-commander version:** (output of `python -c "import incident_commander; print(incident_commander.__version__)"`)
- **Python version:** (output of `python --version`)
- **OS:** (macOS, Linux)
- **LLM model:** (e.g. `ollama/qwen2.5-coder:7b`, `opencode/deepseek-v4-flash`)
- **Mode:** (`simulate` or `run`)

## Simulation JSON (if applicable)
```json
{
  "service": "...",
  "severity": "..."
}
```

## Logs
```
Paste any relevant error output or llm-calls.jsonl entries here.
```
