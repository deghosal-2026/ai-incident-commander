"""Parse log files in ``.log``, ``.json``, and ``.md`` formats into ``LogEntry`` objects.

Supported formats:

- ``.log`` — each line matches ``TIMESTAMP LEVEL SOURCE: MESSAGE``
- ``.json`` — a JSON array of log entry objects
- ``.md``  — Markdown with fenced code blocks containing log lines
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from incident_commander.models.state import LogEntry

# Pattern for .log files: TIMESTAMP LEVEL SOURCE: MESSAGE
# Example: ``2026-07-13T14:05:00 ERROR payment-service: Connection pool exhausted``
# \S+? for source makes the colon a non-greedy delimiter, allowing colons in the message
_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\S+)\s+"
    r"(?P<level>DEBUG|INFO|WARN|ERROR|FATAL|TRACE)\s+"
    r"(?P<source>\S+?):\s+"
    r"(?P<message>.+)$"
)

# ISO 8601 variants we accept for the timestamp portion
_ISO_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
    re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"),
    re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"),
    # Slash-separated dates — converted to hyphens before fromisoformat
    re.compile(r"(\d{4})/(\d{2})/(\d{2}) (\d{2}:\d{2}:\d{2})"),
]

# Pattern to extract fenced code blocks from markdown
_CODE_BLOCK_RE = re.compile(
    r"```(?:\w+)?\n(.*?)```", re.DOTALL
)


def _parse_timestamp(raw: str) -> datetime | None:
    """Try to parse a timestamp string using known ISO patterns."""
    for pattern in _ISO_PATTERNS:
        m = pattern.search(raw)
        if m:
            try:
                ts_str = m.group(0)
                # Handle slash-separated dates by converting to hyphens
                if "/" in ts_str:
                    ts_str = ts_str.replace("/", "-")
                return datetime.fromisoformat(ts_str)
            except (ValueError, TypeError):
                continue
    # Unix epoch (seconds) — fallback for numeric timestamps
    # OSError catches platform-specific range errors (e.g. dates before 1970 on Windows)
    try:
        return datetime.fromtimestamp(float(raw))
    except (ValueError, TypeError, OSError):
        pass
    return None


def _parse_log_text(text: str) -> list[LogEntry]:
    """Parse a block of text that may contain log lines."""
    entries: list[LogEntry] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _LOG_LINE_RE.match(line)
        if m:
            # Fall back to now if timestamp can't be parsed; keeps pipeline running
            ts = _parse_timestamp(m.group("timestamp")) or datetime.now()
            entries.append(
                LogEntry(
                    timestamp=ts,
                    level=m.group("level"),  # type: ignore[arg-type]
                    message=m.group("message"),
                    source=m.group("source"),
                )
            )
    return entries


def parse_log_file(path: str | Path) -> list[LogEntry]:
    """Parse a single log file and return a list of ``LogEntry`` objects.

    The parsing strategy depends on the file extension:

    - ``.log`` — each line parsed with the standard timestamp pattern
    - ``.json`` — parsed as a JSON array of log entry dicts
    - ``.md`` — fenced code blocks are extracted and parsed as log lines
    - Other extensions — skipped, returns empty list

    Args:
        path: Path to the log file.

    Returns:
        A list of parsed ``LogEntry`` objects.  Returns an empty list for
        empty files, unknown extensions, or files with no parseable lines.

    
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Log file not found: {p}")

    # errors="replace" lets us ingest files with non-UTF-8 bytes instead of crashing
    raw = p.read_text(encoding="utf-8", errors="replace")
    if not raw.strip():
        return []

    suffix = p.suffix.lower()

    if suffix == ".log":
        return _parse_log_text(raw)

    if suffix == ".json":
        return _parse_json_log(raw, str(p))

    if suffix == ".md":
        return _parse_markdown_log(raw)

    return []


def _parse_json_log(raw: str, source: str) -> list[LogEntry]:
    """Parse a JSON log file into ``LogEntry`` objects.

    The ``source`` parameter (file path) is used as the default ``source``
    field on each LogEntry when the JSON item doesn't provide one.
    """
    try:
        data: list[dict[str, Any]] = json.loads(raw)
    except json.JSONDecodeError:
        return []

    entries: list[LogEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            entry = LogEntry.model_validate(item)
            # Fall back to file path if the JSON item has no source field
            if not entry.source:
                entry = entry.model_copy(update={"source": source})
            entries.append(entry)
        except ValidationError:
            # Skip malformed items individually so one bad entry doesn't lose all logs
            continue
    return entries


def _parse_markdown_log(raw: str) -> list[LogEntry]:
    """Extract code blocks from markdown and parse them as log lines."""
    entries: list[LogEntry] = []
    for m in _CODE_BLOCK_RE.finditer(raw):
        block = m.group(1).strip()
        if block:
            entries.extend(_parse_log_text(block))
    return entries
