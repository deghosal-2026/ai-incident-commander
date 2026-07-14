"""Normalize incident input data from multiple formats to Pydantic models.

Each ``_normalize_*`` function accepts data as:
  - A Pydantic model instance (pass-through)
  - A dict (converted to model)
  - A file path string or Path (read and parse, then convert)

None inputs return an empty list (or raise for the required ``alert`` field).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from incident_commander.models.input import Runbook
from incident_commander.models.state import Alert, ChatMessage, GitHubPR, LogEntry

PathLike = str | Path
AlertSource = Alert | dict[str, Any] | PathLike
LogsSource = list[LogEntry] | list[dict[str, Any]] | PathLike | None
MessagesSource = list[ChatMessage] | list[dict[str, Any]] | PathLike | None
GitHubSource = list[GitHubPR] | list[dict[str, Any]] | PathLike | None
RunbooksSource = list[Runbook] | list[dict[str, Any]] | None


def _read_json(path: PathLike) -> Any:  # noqa: ANN401
    """Read and parse a JSON file. Raises FileNotFoundError or JSONDecodeError."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    with open(p) as f:
        return json.load(f)



def _load_json_dir(dir_path: PathLike) -> list[dict[str, Any]]:
    """Load all JSON files from a directory, sorted by filename."""
    d = Path(dir_path)
    if not d.is_dir():
        raise FileNotFoundError(f"Directory not found: {d}")
    entries: list[dict[str, Any]] = []
    for child in sorted(d.iterdir()):
        if child.suffix == ".json":
            with open(child) as f:
                data = json.load(f)
            # Accept both a single JSON object or an array at the file root
            if isinstance(data, list):
                entries.extend(data)
            else:
                entries.append(data)
    return entries


def _normalize_alert(alert: AlertSource) -> Alert:
    """Normalize an alert to an ``Alert`` instance.

    Accepts:
      - An ``Alert`` object (pass-through)
      - A dict with Alert-compatible fields
      - A ``str`` or ``Path`` pointing to a JSON file containing alert data
    """
    # Pass-through: already a validated Alert
    if isinstance(alert, Alert):
        return alert
    # Dict → Pydantic model validation
    if isinstance(alert, dict):
        return Alert.model_validate(alert)
    # File path → read JSON, then validate as Alert
    if isinstance(alert, (str, Path)):
        data = _read_json(alert)
        if isinstance(data, dict):
            return Alert.model_validate(data)
        raise TypeError(f"Expected a dict in alert file, got {type(data).__name__}")
    raise TypeError(
        f"Expected Alert, dict, str, or Path, got {type(alert).__name__}"
    )


def _normalize_logs(logs: LogsSource) -> list[LogEntry]:
    """Normalize logs to a list of ``LogEntry`` instances.

    Accepts:
      - ``None`` → empty list
      - A list of ``LogEntry`` objects (pass-through)
      - A list of dicts (each validated as LogEntry)
      - A ``str`` or ``Path`` pointing to a log directory or file
    """
    if logs is None:
        return []
    if isinstance(logs, list):
        result: list[LogEntry] = []
        for item in logs:
            if isinstance(item, LogEntry):
                result.append(item)
            elif isinstance(item, dict):
                result.append(LogEntry.model_validate(item))
            else:
                raise TypeError(
                    f"Expected LogEntry or dict in list, got {type(item).__name__}"
                )
        return result
    if isinstance(logs, (str, Path)):
        p = Path(logs)
        # If path is a directory, load all JSON/log files from it
        if p.is_dir():
            return _normalize_logs(_load_json_dir(p))
        # Single file: read JSON array and recurse back through the list branch above
        raw = _read_json(p)
        if isinstance(raw, list):
            return _normalize_logs(raw)
        raise TypeError(f"Expected a list in log file, got {type(raw).__name__}")
    raise TypeError(
        f"Expected list, str, Path, or None, got {type(logs).__name__}"
    )


def _normalize_messages(messages: MessagesSource) -> list[ChatMessage]:
    """Normalize chat messages to a list of ``ChatMessage`` instances.

    Accepts:
      - ``None`` → empty list
      - A list of ``ChatMessage`` objects (pass-through)
      - A list of dicts (each validated as ChatMessage)
      - A ``str`` or ``Path`` pointing to a JSON file containing messages
    """
    if messages is None:
        return []
    if isinstance(messages, list):
        result: list[ChatMessage] = []
        for item in messages:
            if isinstance(item, ChatMessage):
                result.append(item)
            elif isinstance(item, dict):
                result.append(ChatMessage.model_validate(item))
            else:
                raise TypeError(
                    f"Expected ChatMessage or dict in list, got {type(item).__name__}"
                )
        return result
    if isinstance(messages, (str, Path)):
        raw = _read_json(messages)
        if isinstance(raw, list):
            return _normalize_messages(raw)
        raise TypeError(
            f"Expected a list in messages file, got {type(raw).__name__}"
        )
    raise TypeError(
        f"Expected list, str, Path, or None, got {type(messages).__name__}"
    )


def _normalize_github(github: GitHubSource) -> list[GitHubPR]:
    """Normalize GitHub PR data to a list of ``GitHubPR`` instances.

    Accepts:
      - ``None`` → empty list
      - A list of ``GitHubPR`` objects (pass-through)
      - A list of dicts (each validated as GitHubPR)
      - A ``str`` or ``Path`` pointing to a JSON file containing PR data
    """
    if github is None:
        return []
    if isinstance(github, list):
        result: list[GitHubPR] = []
        for item in github:
            if isinstance(item, GitHubPR):
                result.append(item)
            elif isinstance(item, dict):
                result.append(GitHubPR.model_validate(item))
            else:
                raise TypeError(
                    f"Expected GitHubPR or dict in list, got {type(item).__name__}"
                )
        return result
    if isinstance(github, (str, Path)):
        raw = _read_json(github)
        if isinstance(raw, list):
            return _normalize_github(raw)
        raise TypeError(
            f"Expected a list in github file, got {type(raw).__name__}"
        )
    raise TypeError(
        f"Expected list, str, Path, or None, got {type(github).__name__}"
    )


def _normalize_runbooks(runbooks: RunbooksSource) -> list[Runbook]:
    """Normalize runbooks to a list of ``Runbook`` instances.

    Accepts:
      - ``None`` → empty list
      - A list of ``Runbook`` objects (pass-through)
      - A list of dicts (each validated as Runbook)
    """
    if runbooks is None:
        return []
    if isinstance(runbooks, list):
        result: list[Runbook] = []
        for item in runbooks:
            if isinstance(item, Runbook):
                result.append(item)
            elif isinstance(item, dict):
                result.append(Runbook.model_validate(item))
            else:
                raise TypeError(
                    f"Expected Runbook or dict in list, got {type(item).__name__}"
                )
        return result
    raise TypeError(
        f"Expected list or None, got {type(runbooks).__name__}"
    )


def normalize(
    alert: AlertSource,
    logs: LogsSource = None,
    messages: MessagesSource = None,
    github: GitHubSource = None,
    runbooks: RunbooksSource = None,
) -> dict[str, Any]:
    """Normalize all input channels into a dict of Pydantic models.

    This is the public entry point used by ``run_incident()`` in api.py.
    Returns a dict with keys: alert, logs, messages, github, runbooks.
    """
    return {
        "alert": _normalize_alert(alert),
        "logs": _normalize_logs(logs),
        "messages": _normalize_messages(messages),
        "github": _normalize_github(github),
        "runbooks": _normalize_runbooks(runbooks),
    }
