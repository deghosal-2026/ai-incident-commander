"""Tests for deploy correlation: correlate_deploys_node window, strength, markers."""

from __future__ import annotations

from datetime import datetime, timedelta  # datetime math for PR/alert time deltas

import pytest

# Domain models needed to construct test alert, PRs, and timeline events
from incident_commander.models import Alert, GitHubPR, IncidentState, TimelineEvent

# Constants and function under test from the deploy correlation node
from incident_commander.nodes.deploy_correlation import (
    DEFAULT_WINDOW_MINUTES,
    STRONG_THRESHOLD_MINUTES,
    correlate_deploys_node,
)

# Fixed alert time; all PR merge times are offset relative to this reference
NOW = datetime(2026, 7, 12, 12, 0, 0)


def make_state(
    alert_time: datetime | None = None,
    prs: list[GitHubPR] | None = None,
    timeline: list[TimelineEvent] | None = None,
) -> IncidentState:
    """Build state with alert and optional PRs/timeline."""
    # Default alert time to NOW if not overridden by the caller
    if alert_time is None:
        alert_time = NOW
    return IncidentState(
        severity="SEV1",
        service="payment-service",
        alert=Alert(
            severity="SEV1",
            service="payment-service",
            summary="Error spike",
            timestamp=alert_time,
        ),
        # Empty lists if not provided so guard-clause tests have clean state
        input_prs=prs or [],
        timeline=timeline or [],
    )


def make_pr(
    merge_time: datetime,
    number: int = 100,
    title: str = "fix: resolve pool leak",
) -> GitHubPR:
    """Build a GitHub PR with given merge time."""
    # Defaults: PR #100 by "dev" with deploy label and src/main.py changed
    return GitHubPR(
        number=number,
        title=title,
        author="dev",
        merge_time=merge_time,
        files_changed=["src/main.py"],
        labels=["deploy"],
    )


def make_timeline_event(source: str = "github", content: str = "PR #100 merged") -> TimelineEvent:
    """Build a timeline event for deploy correlation testing."""
    # Defaults: github PR-merged event 5 min before NOW with high trust level
    return TimelineEvent(
        timestamp=NOW - timedelta(minutes=5),
        source=source,
        # event_type depends on source: github→pr_merged, others→message
        event_type="pr_merged" if source == "github" else "message",
        content=content,
        trust_level="high",
    )


class TestCorrelateDeploysNode:
    """correlate_deploys_node: correlates PRs with alert timestamp."""

    def test_strong_correlation(self) -> None:
        """PR merged 10 min before alert → strong correlation."""
        # 10 min is within 15-min strong threshold → strength="strong"
        pr = make_pr(merge_time=NOW - timedelta(minutes=10))
        state = make_state(prs=[pr])
        result = correlate_deploys_node(state)
        assert len(result.deploy_correlations) == 1
        assert result.deploy_correlations[0].correlation_strength == "strong"
        # minutes_before_alert should exactly match the 10-min delta
        assert result.deploy_correlations[0].minutes_before_alert == 10

    def test_weak_correlation(self) -> None:
        """PR merged 20 min before alert → weak correlation."""
        # 20 min exceeds 15-min strong threshold but is within 30-min window
        pr = make_pr(merge_time=NOW - timedelta(minutes=20))
        state = make_state(prs=[pr])
        result = correlate_deploys_node(state)
        assert len(result.deploy_correlations) == 1
        assert result.deploy_correlations[0].correlation_strength == "weak"

    def test_outside_window(self) -> None:
        """PR merged 35 min before alert → no correlation (outside 30 min window)."""
        # 35 min exceeds the 30-min DEFAULT_WINDOW_MINUTES → excluded entirely
        pr = make_pr(merge_time=NOW - timedelta(minutes=35))
        state = make_state(prs=[pr])
        result = correlate_deploys_node(state)
        assert result.deploy_correlations == []

    def test_pr_after_alert(self) -> None:
        """PR merged after alert → no correlation (strict-positive boundary)."""
        # PR 5 min after alert → merge_time > alert_time → no correlation
        pr = make_pr(merge_time=NOW + timedelta(minutes=5))
        state = make_state(prs=[pr])
        result = correlate_deploys_node(state)
        assert result.deploy_correlations == []

    def test_pr_at_same_time(self) -> None:
        """PR merged at alert time → no correlation (time_diff must be > 0)."""
        # PR at exact alert time → time_diff is 0, not strictly positive
        pr = make_pr(merge_time=NOW)
        state = make_state(prs=[pr])
        result = correlate_deploys_node(state)
        assert result.deploy_correlations == []

    def test_no_prs(self) -> None:
        """No PRs in input → no correlations, no crash."""
        # Empty PR list → guard clause returns early with no correlations
        state = make_state(prs=[])
        result = correlate_deploys_node(state)
        assert result.deploy_correlations == []

    def test_no_alert(self) -> None:
        """No alert in state → no correlations, no crash."""
        # No alert means no reference timestamp → guard clause returns early
        state = IncidentState(severity="SEV3", service="test")
        result = correlate_deploys_node(state)
        assert result.deploy_correlations == []

    def test_multiple_prs_all_correlated(self) -> None:
        """Multiple PRs within window → all correlated."""
        # 3 PRs at 5, 15, 25 min — all within the 30-min window
        prs = [
            make_pr(merge_time=NOW - timedelta(minutes=5), number=101),
            make_pr(merge_time=NOW - timedelta(minutes=15), number=102),
            make_pr(merge_time=NOW - timedelta(minutes=25), number=103),
        ]
        state = make_state(prs=prs)
        result = correlate_deploys_node(state)
        # All 3 PRs should produce correlation entries
        assert len(result.deploy_correlations) == 3

    def test_timeline_marker_applied(self) -> None:
        """Correlated PR timeline events get deploy_correlation=True."""
        # PR 10 min before alert → strong correlation; matching timeline event
        merge_time = NOW - timedelta(minutes=10)
        pr = make_pr(merge_time=merge_time, number=100)
        event = TimelineEvent(
            timestamp=merge_time,
            source="github",
            event_type="pr_merged",
            content="PR #100 merged: fix: resolve pool leak",
            trust_level="high",
        )
        state = make_state(prs=[pr], timeline=[event])
        result = correlate_deploys_node(state)
        # The correlated github event must be flagged on the timeline
        assert result.timeline[0].deploy_correlation is True

    def test_non_github_events_not_marked(self) -> None:
        """Non-github events are not marked as deploy correlation."""
        # PR is correlated, but the timeline event is an alert, not github
        pr = make_pr(merge_time=NOW - timedelta(minutes=10), number=100)
        event = make_timeline_event(source="alert", content="Error spike")
        state = make_state(prs=[pr], timeline=[event])
        result = correlate_deploys_node(state)
        # Only github events should be flagged; alert events must not be
        assert result.timeline[0].deploy_correlation is False

    def test_strength_at_boundary(self) -> None:
        """PR at exactly 15 min before alert → strong (≤ 15)."""
        # Exactly 15 min → inclusive boundary of strong threshold → strong
        pr = make_pr(merge_time=NOW - timedelta(minutes=15))
        state = make_state(prs=[pr])
        result = correlate_deploys_node(state)
        assert result.deploy_correlations[0].correlation_strength == "strong"

    def test_strength_just_over_boundary(self) -> None:
        """PR at 16 min before alert → weak (> 15)."""
        # 16 min is just 1 min over the strong threshold → weak
        pr = make_pr(merge_time=NOW - timedelta(minutes=16))
        state = make_state(prs=[pr])
        result = correlate_deploys_node(state)
        assert result.deploy_correlations[0].correlation_strength == "weak"

    def test_window_minutes_constant(self) -> None:
        """DEFAULT_WINDOW_MINUTES and STRONG_THRESHOLD_MINUTES have expected values."""
        # 30-min window and 15-min strong threshold are the documented constants
        assert DEFAULT_WINDOW_MINUTES == 30
        assert STRONG_THRESHOLD_MINUTES == 15

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "TODO: deploy_correlation_window_minutes config not wired to node. "
            "Node hardcodes DEFAULT_WINDOW_MINUTES=30 and ignores config."
        ),
    )
    def test_config_window_not_wired_yet(self) -> None:
        """PR 20 min before alert — currently correlated (config window not wired)."""
        pr = make_pr(merge_time=NOW - timedelta(minutes=20))
        state = make_state(prs=[pr])
        result = correlate_deploys_node(state)
        assert result.deploy_correlations == []
