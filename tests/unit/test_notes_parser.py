"""Tests for the notes_parser module: parse_notes_to_events."""

from __future__ import annotations

from datetime import datetime

from incident_commander.ingest.notes_parser import _parse_timestamp, parse_notes_to_events


class TestParseNotesToEvents:
    """parse_notes_to_events — parses markdown headings into TimelineEvents."""

    def test_three_headings_three_events(self) -> None:
        """Notes with 3 headings produce 3 TimelineEvents."""
        # Each `## HH:MM — Title` block becomes a separate TimelineEvent
        notes = (
            "## 14:05 — First responder notices spike\nTraffic spiking\n\n"
            "## 14:10 — Page sent\nPage sent to oncall\n\n"
            "## 14:15 — Investigation started\nLooking at logs\n"
        )
        events = parse_notes_to_events(notes)
        assert len(events) == 3

    def test_trust_level_low(self) -> None:
        """All events have trust_level 'low'."""
        # Human-entered notes always get lowest trust — unverified, potentially inaccurate
        notes = "## 14:05 — Something happened\nDetail"
        events = parse_notes_to_events(notes)
        assert all(e.trust_level == "low" for e in events)

    def test_source_manual(self) -> None:
        """All events have source 'manual'."""
        notes = "## 14:05 — Event\nDetail"
        events = parse_notes_to_events(notes)
        assert all(e.source == "manual" for e in events)

    def test_timestamp_from_heading(self) -> None:
        """Timestamp extracted from heading if present."""
        # Parser extracts HH:MM from the heading and uses today's date
        notes = "## 14:05 — First event\nDetail"
        events = parse_notes_to_events(notes)
        assert len(events) == 1
        assert events[0].timestamp.hour == 14
        assert events[0].timestamp.minute == 5

    def test_empty_notes_returns_empty(self) -> None:
        """Empty string returns empty list."""
        assert parse_notes_to_events("") == []

    def test_no_headings_returns_empty(self) -> None:
        """Text without headings returns empty list."""
        # No `##` headings — parser returns [] instead of crashing
        assert parse_notes_to_events("Some plain text\nwithout headings\n") == []

    def test_content_under_heading(self) -> None:
        """Content under heading becomes event content."""
        # Body text after the heading line is captured as the event's content string
        notes = "## 14:05 — Spike\nCPU usage went to 100%"
        events = parse_notes_to_events(notes)
        assert len(events) == 1
        assert "CPU" in events[0].content

    def test_heading_becomes_event_type(self) -> None:
        """Heading text becomes the event_type."""
        # The heading title (after timestamp) maps to TimelineEvent.event_type
        notes = "## 14:05 — Spike detected"
        events = parse_notes_to_events(notes)
        assert "Spike detected" in events[0].event_type


class TestParseTimestamp:
    """_parse_timestamp — timestamp extraction from various patterns."""

    def test_invalid_hhmm_returns_none(self) -> None:
        """Invalid HH:MM (25:99) returns None."""
        ts = _parse_timestamp("## 25:99 — bad")
        assert ts is None

    def test_invalid_iso_returns_none(self) -> None:
        """Invalid ISO date returns None."""
        ts = _parse_timestamp("## 2026-13-45T99:99:99")
        assert ts is None

    def test_iso_with_t_separator(self) -> None:
        """ISO 8601 with T separator parses correctly."""
        ts = _parse_timestamp("2026-07-13T14:05:00")
        assert ts is not None
        assert ts == datetime(2026, 7, 13, 14, 5, 0)

    def test_space_separator(self) -> None:
        """ISO 8601 with space separator parses correctly."""
        ts = _parse_timestamp("2026-07-13 14:05:00")
        assert ts is not None
        assert ts == datetime(2026, 7, 13, 14, 5, 0)

    def test_hhmm_only(self) -> None:
        """HH:MM only — timestamp is today at that time."""
        ts = _parse_timestamp("## 14:05")
        assert ts is not None
        now = datetime.now()
        assert ts.date() == now.date()
        assert ts.hour == 14
        assert ts.minute == 5
