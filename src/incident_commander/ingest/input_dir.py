"""Load a structured incident input directory into an ``IncidentInput`` object.

Directory layout::

    incident-YYYY-NNN/
    ├── meta.json           # required — incident metadata
    ├── alert.json          # required — triggering alert payload
    ├── logs/               # optional — log files (.log, .json, .md)
    ├── messages.json       # optional — chat/message export
    ├── github.json         # optional — GitHub PR data
    ├── runbooks/           # optional — runbook files
    └── notes.md            # optional — free-form incident notes
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from incident_commander.ingest.log_parser import parse_log_file
from incident_commander.ingest.normalizer import (
    _normalize_alert,
    _normalize_github,
    _normalize_logs,
    _normalize_messages,
    _normalize_runbooks,
)
from incident_commander.ingest.notes_parser import parse_notes_to_events
from incident_commander.models.input import IncidentInput, IncidentMeta
from incident_commander.models.state import TimelineEvent


class InputDirLoader:
    """Loads all supported files from a structured incident input directory.

    The directory must contain at least ``meta.json`` and ``alert.json``.
    All other files and sub-directories are optional — missing optional
    inputs are silently replaced with defaults (empty lists / ``None``).

    Args:
        directory: Path to the incident input directory.

    """

    def __init__(self, directory: str | Path) -> None:
        """Initialize the loader with a path to the input directory."""
        self._directory = Path(directory)

    def load(self) -> IncidentInput:
        """Load and return a fully populated ``IncidentInput``.

        Raises:
            FileNotFoundError: If the directory or a required file
                (``meta.json``, ``alert.json``) is missing.
            json.JSONDecodeError: If any JSON file is malformed; the
                exception message includes the file path.

        """
        _dir = self._directory
        if not _dir.is_dir():
            raise FileNotFoundError(f"Input directory not found: {_dir}")

        # ── Required files ──────────────────────────────────────────
        meta_dict = self._load_required_json("meta.json")
        alert_dict = self._load_required_json("alert.json")

        # ── Optional files / directories ─────────────────────────────
        logs_list = self._load_optional_logs()
        messages_data = self._load_optional_json("messages.json")
        github_data = self._load_optional_json("github.json")
        runbooks_list = self._load_optional_runbooks()
        manual_events = self._load_optional_notes()

        return IncidentInput(
            schema_version="0.1.0",
            alert=_normalize_alert(alert_dict),
            logs=_normalize_logs(logs_list) if logs_list else [],
            messages=_normalize_messages(messages_data) if messages_data is not None else [],
            github=_normalize_github(github_data) if github_data is not None else [],
            runbooks=_normalize_runbooks(runbooks_list) if runbooks_list else [],
            manual_events=manual_events,
            meta=IncidentMeta.model_validate(meta_dict),
        )

    # ── Internal helpers ────────────────────────────────────────────

    def _path(self, name: str) -> Path:
        """Resolve a filename relative to the input directory."""
        return self._directory / name

    def _load_required_json(self, filename: str) -> dict[str, Any]:
        """Read and parse a required JSON file, raising on failure."""
        path = self._path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")
        try:
            with open(path) as f:
                data: Any = json.load(f)
            if not isinstance(data, dict):
                raise TypeError(f"Expected a dict in {path}, got {type(data).__name__}")
            return data
        except json.JSONDecodeError as exc:
            # Re-raise with file path so callers can identify which file is broken
            raise json.JSONDecodeError(
                f"Malformed JSON in {path}: {exc.msg}", exc.doc, exc.pos
            ) from exc

    def _load_optional_json(self, filename: str) -> Any | None:  # noqa: ANN401
        """Read an optional JSON file, returning ``None`` if absent.

        The caller is responsible for checking the returned type
        (typically ``dict`` or ``list``).
        """
        path = self._path(filename)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError(
                f"Malformed JSON in {path}: {exc.msg}", exc.doc, exc.pos
            ) from exc

    def _load_optional_logs(self) -> list[dict[str, Any]] | None:
        """Load all log files from the ``logs/`` sub-directory."""
        logs_dir = self._path("logs")
        if not logs_dir.is_dir():
            return None
        entries: list[dict[str, Any]] = []
        for child in sorted(logs_dir.iterdir()):
            # Only process known log formats; silently skip .txt, .csv, etc.
            if child.is_file() and child.suffix in (".log", ".json", ".md"):
                parsed = parse_log_file(child)
                # Convert back to dict for serialization through the normalizer pipeline
                for entry in parsed:
                    entries.append(entry.model_dump())
        if not entries:
            return []
        return entries

    def _load_optional_runbooks(self) -> list[dict[str, Any]] | None:
        """Load runbook files from the ``runbooks/`` sub-directory."""
        runbooks_dir = self._path("runbooks")
        if not runbooks_dir.is_dir():
            return None
        entries: list[dict[str, Any]] = []
        for child in sorted(runbooks_dir.iterdir()):
            if child.suffix == ".json":
                try:
                    with open(child) as f:
                        data = json.load(f)
                    # Accept both a single runbook dict or an array of them
                    if isinstance(data, list):
                        entries.extend(data)
                    else:
                        entries.append(data)
                except json.JSONDecodeError as exc:
                    raise json.JSONDecodeError(
                        f"Malformed JSON in {child}: {exc.msg}", exc.doc, exc.pos
                    ) from exc
        return entries if entries else []

    def _load_optional_notes(self) -> list[TimelineEvent]:
        """Load and parse the optional ``notes.md`` file."""
        path = self._path("notes.md")
        if not path.exists():
            return []
        content = path.read_text(encoding="utf-8")
        return parse_notes_to_events(content)
