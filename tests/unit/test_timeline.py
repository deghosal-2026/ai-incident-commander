"""Tests for the timeline builder module."""

from __future__ import annotations

from datetime import datetime, timedelta  # datetime math for event timestamps
from typing import Any  # Any used for flexible override dict typing

# Core domain models: Alert, ChatMessage, GitHubPR, LogEntry, TimelineEvent
from incident_commander.models import (
    Alert,
    ChatMessage,
    GitHubPR,
    IncidentState,
    LogEntry,
    TimelineEvent,
)

# Timeline node functions: build, add, format, and summarize timeline events
from incident_commander.nodes.timeline import (
    add_event,
    build_timeline_node,
    format_timeline,
    get_timeline_summary,
)

# Fixed reference time so all test timestamps are deterministic and comparable
NOW = datetime(2026, 7, 12, 12, 0, 0)


def make_state(**overrides: object) -> IncidentState:
    """Build an IncidentState with defaults suitable for timeline tests."""
    # Default to SEV3 on test-service; no alert so empty-state tests work
    defaults: dict[str, Any] = {
        "severity": "SEV3", "service": "test-service", "incident_id": "test-001",
    }
    defaults.update(overrides)  # callers override only the fields they need
    return IncidentState(**defaults)


class TestBuildTimelineNode:
    """build_timeline_node merges multi-source events into chronological order."""

    def test_empty_state(self) -> None:
        """No alert + no input data → empty timeline, no crash."""
        # No alert and no input data → timeline must be empty, not an error
        state = make_state()
        result = build_timeline_node(state)
        assert result.timeline == []

    def test_alert_only(self) -> None:
        """Alert alone produces one timeline event."""
        state = make_state(
            alert=Alert(
                severity="SEV1",
                service="payment-service",
                summary="Error spike",
                timestamp=NOW,
            ),
        )
        result = build_timeline_node(state)
        # Single alert produces exactly one timeline event
        assert len(result.timeline) == 1
        # Alert events are tagged source="alert" with high trust level
        assert result.timeline[0].source == "alert"
        assert result.timeline[0].trust_level == "high"

    def test_alert_and_logs(self) -> None:
        """Alert + log entries → 2 events sorted chronologically."""
        state = make_state(
            alert=Alert(
                severity="SEV1", service="payment-service", summary="Error spike", timestamp=NOW,
            ),
            input_logs=[
                LogEntry(
                    # Log 5 min before alert to test chronological ordering
                    timestamp=NOW - timedelta(minutes=5),
                    level="ERROR",
                    message="Timeout",
                    source="payment-service",
                ),
            ],
        )
        result = build_timeline_node(state)
        # Two events: log (earlier) then alert (later) in chronological order
        assert len(result.timeline) == 2
        assert result.timeline[0].source == "log"
        assert result.timeline[1].source == "alert"

    def test_all_sources(self) -> None:
        """Events from alert, log, chat, github → all present in timeline."""
        state = make_state(
            alert=Alert(
                severity="SEV2", service="api-gateway", summary="Latency spike", timestamp=NOW,
            ),
            input_logs=[
                LogEntry(
                    # Log 3 min before alert
                    timestamp=NOW - timedelta(minutes=3),
                    level="WARN",
                    message="High latency",
                    source="api-gateway",
                ),
            ],
            input_messages=[
                ChatMessage(
                    # Chat 2 min before alert
                    timestamp=NOW - timedelta(minutes=2),
                    author="bob",
                    text="Checking logs",
                    channel="#incidents",
                ),
            ],
            input_prs=[
                GitHubPR(
                    # PR 1 min before alert
                    number=101,
                    title="fix: update config",
                    author="dev",
                    merge_time=NOW - timedelta(minutes=1),
                ),
            ],
        )
        result = build_timeline_node(state)
        # All 4 input channels must produce timeline events
        sources = {e.source for e in result.timeline}
        assert sources == {"alert", "log", "chat", "github"}

    def test_chronological_order(self) -> None:
        """Events sorted by timestamp ascending."""
        state = make_state(
            alert=Alert(severity="SEV3", service="test", summary="test", timestamp=NOW),
            input_logs=[
                LogEntry(
                    # First log at -10 min (earliest)
                    timestamp=NOW - timedelta(minutes=10),
                    level="INFO",
                    message="first",
                    source="test",
                ),
                LogEntry(
                    # Second log at -5 min (middle)
                    timestamp=NOW - timedelta(minutes=5),
                    level="WARN",
                    message="second",
                    source="test",
                ),
                LogEntry(
                    # Third log at -1 min (latest before alert)
                    timestamp=NOW - timedelta(minutes=1),
                    level="ERROR",
                    message="third",
                    source="test",
                ),
            ],
        )
        result = build_timeline_node(state)
        # Verify every adjacent pair is in ascending timestamp order
        for i in range(len(result.timeline) - 1):
            assert result.timeline[i].timestamp <= result.timeline[i + 1].timestamp

    def test_same_timestamp_stable_sort(self) -> None:
        """Events with same timestamp sorted by trust level (high first)."""
        state = make_state(
            alert=Alert(severity="SEV3", service="test", summary="test", timestamp=NOW),
            input_logs=[
                # All events at same NOW to test trust-level tiebreaker
                LogEntry(timestamp=NOW, level="ERROR", message="error log", source="test"),
            ],
            input_messages=[
                ChatMessage(
                    timestamp=NOW,
                    author="alice",
                    text="chat message",
                    channel="#incidents",
                ),
            ],
        )
        result = build_timeline_node(state)
        # Find indices to verify trust-level ordering (high before medium)
        alert_idx = next(i for i, e in enumerate(result.timeline) if e.source == "alert")
        log_idx = next(i for i, e in enumerate(result.timeline) if e.source == "log")
        chat_idx = next(i for i, e in enumerate(result.timeline) if e.source == "chat")
        # alert=high must come before chat=high and log=medium in tiebreaker
        assert alert_idx < chat_idx  # alert=high, chat=high, log=medium
        assert alert_idx < log_idx

    def test_trust_level_per_source(self) -> None:
        """Trust hierarchy: alert/chat/github=high, log=medium, manual=low."""
        state = make_state(
            alert=Alert(severity="SEV3", service="test", summary="test", timestamp=NOW),
            input_logs=[LogEntry(timestamp=NOW, level="ERROR", message="log", source="test")],
            input_messages=[
                ChatMessage(timestamp=NOW, author="alice", text="chat", channel="#incidents"),
            ],
            input_prs=[GitHubPR(number=1, title="fix", author="dev", merge_time=NOW)],
            input_manual_events=[
                TimelineEvent(
                    timestamp=NOW,
                    source="manual",
                    event_type="note",
                    content="manual entry",
                    # Manual events are always low trust (human-entered, unverified)
                    trust_level="low",
                ),
            ],
        )
        result = build_timeline_node(state)
        # Build source→trust map and verify the full trust hierarchy
        trust_map = {e.source: e.trust_level for e in result.timeline}
        assert trust_map["alert"] == "high"
        assert trust_map["chat"] == "high"
        assert trust_map["github"] == "high"
        assert trust_map["log"] == "medium"
        assert trust_map["manual"] == "low"

    def test_manual_events_extended(self) -> None:
        """Manual events from input_manual_events are appended with trust_level='low'."""
        manual = TimelineEvent(
            timestamp=NOW,
            source="manual",
            event_type="note",
            content="Commander note",
            trust_level="low",
        )
        state = make_state(
            alert=Alert(severity="SEV3", service="test", summary="test", timestamp=NOW),
            input_manual_events=[manual],
        )
        result = build_timeline_node(state)
        # Manual events must appear in timeline and preserve their low trust level
        assert any(e.source == "manual" for e in result.timeline)
        manual_event = next(e for e in result.timeline if e.source == "manual")
        assert manual_event.trust_level == "low"


class TestAddEvent:
    """add_event appends to timeline maintaining sort order."""

    def test_add_to_empty(self) -> None:
        """Adding event to empty timeline creates one entry."""
        state = make_state()
        event = TimelineEvent(
            timestamp=NOW,
            source="manual",
            event_type="note",
            content="test",
            trust_level="low",
        )
        result = add_event(state, event)
        # Empty timeline + one event → exactly one entry with correct content
        assert len(result.timeline) == 1
        assert result.timeline[0].content == "test"

    def test_add_maintains_order(self) -> None:
        """Adding event preserves chronological order."""
        state = make_state(
            alert=Alert(severity="SEV3", service="test", summary="test", timestamp=NOW),
        )
        state = build_timeline_node(state)
        # New event 10 min after NOW should land at the end of the timeline
        later = TimelineEvent(
            timestamp=NOW + timedelta(minutes=10),
            source="manual",
            event_type="note",
            content="later",
            trust_level="low",
        )
        result = add_event(state, later)
        # Re-sorted timeline places the later event at the end
        assert result.timeline[-1].content == "later"


class TestFormatFunctions:
    """format_timeline and get_timeline_summary produce human-readable output."""

    def test_format_timeline_empty(self) -> None:
        """Empty timeline → empty string."""
        # Empty list should return empty string, not crash or produce headers
        assert format_timeline([]) == ""

    def test_format_timeline_with_events(self) -> None:
        """Non-empty timeline returns formatted lines."""
        events = [
            TimelineEvent(
                timestamp=NOW,
                source="alert",
                event_type="alert_fired",
                content="Error spike",
                trust_level="high",
            ),
        ]
        output = format_timeline(events)
        # Event content must appear in formatted output
        assert "Error spike" in output
        # High-trust events omit the trust marker (only medium/low show it)
        assert "trust:" not in output  # high trust → no trust marker

    def test_format_timeline_medium_trust(self) -> None:
        """Medium trust events show trust marker."""
        events = [
            TimelineEvent(
                timestamp=NOW,
                source="log",
                event_type="error",
                content="timeout",
                trust_level="medium",
            ),
        ]
        output = format_timeline(events)
        # Medium-trust events display "(trust: medium)" marker for visibility
        assert "(trust: medium)" in output

    def test_format_timeline_low_trust(self) -> None:
        """Low trust events show special marker."""
        events = [
            TimelineEvent(
                timestamp=NOW,
                source="manual",
                event_type="note",
                content="note",
                trust_level="low",
            ),
        ]
        output = format_timeline(events)
        # Low-trust events show "LOW" marker to flag unverified human input
        assert "LOW" in output

    def test_format_timeline_deploy_correlation(self) -> None:
        """Deploy correlated events show marker."""
        events = [
            TimelineEvent(
                timestamp=NOW,
                source="github",
                event_type="pr_merged",
                content="PR #100",
                trust_level="high",
                deploy_correlation=True,
            ),
        ]
        output = format_timeline(events)
        # deploy_correlation=True flag triggers "DEPLOY CORRELATION" marker
        assert "DEPLOY CORRELATION" in output

    def test_get_timeline_summary_empty(self) -> None:
        """Empty timeline → 'No timeline events recorded.'."""
        state = make_state()
        # No events in state → default message, not empty string or crash
        assert get_timeline_summary(state) == "No timeline events recorded."

    def test_get_timeline_summary_with_events(self) -> None:
        """Non-empty timeline returns summary with event details."""
        state = make_state(
            alert=Alert(severity="SEV3", service="test", summary="test alert", timestamp=NOW),
        )
        state = build_timeline_node(state)
        summary = get_timeline_summary(state)
        # Summary must include the alert summary text and [alert] source tag
        assert "test alert" in summary
        assert "[alert]" in summary
