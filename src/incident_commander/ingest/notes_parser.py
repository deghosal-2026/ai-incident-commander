"""Parse free-form notes (``notes.md``) into timeline events.

The notes file uses ``##``-style Markdown headings as event markers.
Each heading line becomes a ``TimelineEvent`` with ``source="manual"``
and ``trust_level="low"``.
"""

from __future__ import annotations

import re
from datetime import datetime

from incident_commander.models.state import TimelineEvent

# Match a `## Heading` line.  Timestamps can appear in the heading text
# (e.g. ``## 14:05 — First responder notices spike``) or as the first
# line of the body content.
_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# Common timestamp patterns we try to extract from heading text.
# ISO 8601 is checked first so full dates aren't truncated to HH:MM.
_TIMESTAMP_PATTERNS: list[re.Pattern[str]] = [
    # ISO 8601 date + time — e.g. "2026-07-13T14:05:00"
    re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)"),
    # HH:MM (24-hour) — e.g. "14:05", "09:30"
    re.compile(r"(\d{1,2}:\d{2})"),
]


def _parse_timestamp(raw: str) -> datetime | None:
    """Try to extract a timestamp from a string, returning None on failure."""
    for pattern in _TIMESTAMP_PATTERNS:
        m = pattern.search(raw)
        if m:
            ts_str = m.group(1)
            # Try HH:MM first, assume today's date (no date in notes → relative time)
            if ":" in ts_str and "-" not in ts_str:
                parts = ts_str.split(":")
                try:
                    now = datetime.now()
                    return now.replace(
                        hour=int(parts[0]),
                        minute=int(parts[1]),
                        second=0,
                        microsecond=0,
                    )
                except (ValueError, TypeError):
                    continue
            # ISO 8601 — fromisoformat prefers space over T separator on some Python versions
            try:
                return datetime.fromisoformat(ts_str.replace("T", " "))
            except (ValueError, TypeError):
                continue
    return None


def parse_notes_to_events(notes_text: str) -> list[TimelineEvent]:
    """Parse a ``notes.md`` string into a list of ``TimelineEvent`` objects.

    Each ``##`` heading becomes one timeline event.  The timestamp is
    extracted from the heading text (or body) if present; otherwise the
    current time is used as a fallback.

    Args:
        notes_text: The raw content of the ``notes.md`` file.

    Returns:
        A list of ``TimelineEvent`` instances.  Returns an empty list
        when the input is empty or contains no ``##`` headings.

    
    """
    if not notes_text or not notes_text.strip():
        return []

    sections = _HEADING_RE.split(notes_text.strip())
    # sections[0] is text before the first heading (preamble) — skip it.
    # The rest is interleaved [heading1, body1, heading2, body2, ...]
    events: list[TimelineEvent] = []
    now = datetime.now()

    for i in range(1, len(sections), 2):
        heading = sections[i].strip()
        body = sections[i + 1].strip() if i + 1 < len(sections) else ""

        # Try heading first, then body for a timestamp; fallback to now if neither matches
        ts = _parse_timestamp(heading) or _parse_timestamp(body) or now

        # Use the heading as the event_type and the body as content
        events.append(
            TimelineEvent(
                timestamp=ts,
                source="manual",
                event_type=heading,
                content=body,
                trust_level="low",
            )
        )

    return events
