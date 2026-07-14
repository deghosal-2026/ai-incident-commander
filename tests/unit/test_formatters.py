"""Tests for output formatters: format_summary_md, format_timeline_md, etc."""

from __future__ import annotations

from incident_commander.models.state import (
    ActionItem,
    CostReport,
    NodeCost,
    Postmortem,
    PostmortemSection,
    RemediationSuggestion,
    StakeholderUpdate,
)
from incident_commander.output.formatters import (
    _section_md,
    format_cost_md,
    format_postmortem_md,
    format_remediation_md,
    format_summary_md,
    format_timeline_md,
    format_updates_md,
)
from tests.conftest import NOW


class TestFormatSummaryMd:
    """format_summary_md — incident summary table."""

    def test_full_result(self) -> None:
        """Full result includes postmortem, cost, deploy, and updates."""
        result = {
            "thread_id": "thread-abc",
            "incident_id": "INC-001",
            "service": "payment-service",
            "severity": "SEV1",
            "postmortem": {"resolved_at": "2026-07-13T12:30:00", "mttr_minutes": 30},
            "cost_report": {"total_estimated_cost_usd": 0.0042, "models_used": ["gpt-4o"]},
            "deploy_correlations": [{"pr_number": 42, "correlation_strength": "strong"}],
            "stakeholder_updates": [
                {"update_number": 1, "impact": "Payment failures affecting users"},
            ],
        }
        out = format_summary_md(result)
        assert "INC-001" in out
        assert "payment-service" in out
        assert "SEV1" in out
        assert "30 min" in out
        assert "$0.0042" in out
        assert "PR #42" in out
        assert "Update 1" in out

    def test_no_postmortem(self) -> None:
        """No postmortem -> no MTTR or Resolved lines."""
        result = {"thread_id": "t1", "incident_id": "I1", "service": "srv", "severity": "SEV2"}
        out = format_summary_md(result)
        assert "Resolved" not in out
        assert "MTTR" not in out

    def test_no_cost_report(self) -> None:
        """No cost report -> no Total Cost line."""
        result = {"thread_id": "t1", "incident_id": "I1", "service": "srv", "severity": "SEV3"}
        out = format_summary_md(result)
        assert "Total Cost" not in out

    def test_no_deploy_correlations(self) -> None:
        """No deploy correlations -> no Deploy Correlation line."""
        result = {
            "thread_id": "t1", "incident_id": "I1", "service": "srv",
            "severity": "SEV3", "deploy_correlations": [],
        }
        out = format_summary_md(result)
        assert "Deploy Correlation" not in out
        assert out.strip()

    def test_no_stakeholder_updates(self) -> None:
        """No stakeholder updates -> no Key Events section."""
        result = {"thread_id": "t1", "incident_id": "I1", "service": "srv", "severity": "SEV3"}
        out = format_summary_md(result)
        assert "Key Events" not in out


class TestFormatTimelineMd:
    """format_timeline_md — chronological timeline table."""

    def test_none_timeline(self) -> None:
        """None -> no timeline message."""
        out = format_timeline_md(None)
        assert "No timeline events recorded" in out

    def test_empty_list(self) -> None:
        """[] -> no timeline message."""
        out = format_timeline_md([])
        assert "No timeline events recorded" in out

    def test_one_event(self) -> None:
        """Single event -> rendered in table."""
        events = [
            {
                "timestamp": "2026-07-13T12:00:00",
                "source": "alert",
                "content": "DB pool exhausted",
                "trust_level": "high",
                "deploy_correlation": False,
            }
        ]
        out = format_timeline_md(events)
        assert "Timeline" in out
        assert "DB pool exhausted" in out
        assert "| Time | Source" in out


class TestFormatUpdatesMd:
    """format_updates_md — stakeholder updates."""

    def test_none_updates(self) -> None:
        """None -> no updates message."""
        out = format_updates_md(None)
        assert "No stakeholder updates drafted" in out

    def test_empty_list(self) -> None:
        """[] -> no updates message."""
        out = format_updates_md([])
        assert "No stakeholder updates drafted" in out

    def test_one_update(self) -> None:
        """Single update rendered with all fields."""
        updates = [
            StakeholderUpdate(
                update_number=1,
                impact="Payment failures",
                root_cause_hypothesis="DB pool",
                action="Rollback",
                next_update_time=NOW,
                confidence=0.85,
                approved=True,
                timestamp=NOW,
            )
        ]
        out = format_updates_md(updates)
        assert "Update 1" in out
        assert "Payment failures" in out
        assert "DB pool" in out
        assert "Rollback" in out
        assert "Approved" in out


class TestFormatRemediationMd:
    """format_remediation_md — remediation suggestions."""

    def test_none_suggestions(self) -> None:
        """None -> no remediation message."""
        out = format_remediation_md(None)
        assert "No remediation suggestions" in out

    def test_empty_list(self) -> None:
        """[] -> no remediation message."""
        out = format_remediation_md([])
        assert "No remediation suggestions" in out

    def test_one_suggestion(self) -> None:
        """Single suggestion rendered without optional fields."""
        suggestions = [
            RemediationSuggestion(
                action="Rollback deploy",
                citation="runbook/rollback.md",
                confidence=0.85,
                dry_run_outcome="",
                similar_incidents=[],
                approved=False,
            )
        ]
        out = format_remediation_md(suggestions)
        assert "Rollback deploy" in out
        assert "runbook/rollback.md" in out
        assert "0.85" in out
        assert "Expected Outcome" not in out
        assert "Similar Incidents" not in out

    def test_with_dry_run_and_similar(self) -> None:
        """Dry run outcome and similar incidents included when present."""
        suggestions = [
            RemediationSuggestion(
                action="Scale up",
                citation="runbook/scale.md",
                confidence=0.9,
                dry_run_outcome="All instances healthy",
                similar_incidents=["INC-001", "INC-002"],
                approved=True,
            )
        ]
        out = format_remediation_md(suggestions)
        assert "Expected Outcome" in out
        assert "All instances healthy" in out
        assert "INC-001" in out


class TestFormatPostmortemMd:
    """format_postmortem_md — COE-format postmortem."""

    def test_none_postmortem(self) -> None:
        """None -> no postmortem message."""
        out = format_postmortem_md(None)
        assert "No postmortem generated" in out

    def test_sev3_no_customer_or_regulatory(self) -> None:
        """SEV3 omits customer_impact, comm_log, regulatory."""
        pm = Postmortem(
            incident_id="INC-001",
            incident_date=NOW,
            severity="SEV3",
            service="web-service",
            summary=PostmortemSection(title="Summary", content="Minor latency spike"),
            timeline=PostmortemSection(
                title="Timeline", content="From session", ai_generated=False,
            ),
            root_cause_analysis=PostmortemSection(
                title="Root Cause Analysis", content="Traffic surge",
            ),
            systemic_contributing_factors=PostmortemSection(
                title="Systemic Factors", content="Auto-scaling slow",
            ),
            action_items=[
                ActionItem(description="Tune threshold", suggested_owner="SRE", priority="P1"),
            ],
            mttr_minutes=None,
        )
        out = format_postmortem_md(pm)
        assert "INC-001" in out
        assert "SEV3" in out
        assert "Traffic surge" in out
        assert "Tune threshold" in out
        assert "Customer Impact" not in out
        assert "Stakeholder Communication Log" not in out
        assert "Regulatory" not in out
        assert "MTTR" not in out

    def test_sev1_with_mttr(self) -> None:
        """SEV1 includes all sections and MTTR."""
        pm = Postmortem(
            incident_id="INC-002",
            incident_date=NOW,
            severity="SEV1",
            service="payment-service",
            summary=PostmortemSection(title="Summary", content="DB outage"),
            timeline=PostmortemSection(title="Timeline", content="Events"),
            root_cause_analysis=PostmortemSection(
                title="Root Cause Analysis", content="Pool exhausted",
            ),
            systemic_contributing_factors=PostmortemSection(
                title="Systemic Factors", content="No circuit breaker",
            ),
            action_items=[
                ActionItem(
                    description="Add circuit breaker", suggested_owner="DB team", priority="P0",
                ),
            ],
            customer_impact=PostmortemSection(title="Customer Impact", content="5% failures"),
            stakeholder_communication_log=PostmortemSection(
                title="Comm Log", content="Updates at 12:05", ai_generated=False,
            ),
            regulatory_compliance_impact=PostmortemSection(
                title="Regulatory Impact", content="None",
            ),
            resolved_at=NOW + __import__("datetime").timedelta(minutes=15),
            mttr_minutes=15,
        )
        out = format_postmortem_md(pm)
        assert "Customer Impact" in out
        assert "Comm Log" in out
        assert "Regulatory" in out
        assert "**MTTR:** 15 minutes" in out

    def test_without_mttr(self) -> None:
        """No MTTR when mttr_minutes is None."""
        pm = Postmortem(
            incident_id="INC-003",
            incident_date=NOW,
            severity="SEV2",
            service="srv",
            summary=PostmortemSection(title="Summary", content="Issue"),
            timeline=PostmortemSection(title="Timeline", content="Events"),
            root_cause_analysis=PostmortemSection(
                title="Root Cause", content="Bug",
            ),
            systemic_contributing_factors=PostmortemSection(
                title="Systemic", content="Missed test",
            ),
            action_items=[],
            mttr_minutes=None,
        )
        out = format_postmortem_md(pm)
        assert "MTTR" not in out


class TestFormatCostMd:
    """format_cost_md — cost report."""

    def test_none_cost(self) -> None:
        """None -> no cost data message."""
        out = format_cost_md(None)
        assert "No cost data available" in out

    def test_empty_per_node(self) -> None:
        """Empty per_node list -> no breakdown table."""
        cr = CostReport(
            session_id="s1",
            total_input_tokens=500,
            total_output_tokens=300,
            total_tokens=800,
            total_estimated_cost_usd=0.001,
            per_node=[],
            models_used=["gpt-4o"],
        )
        out = format_cost_md(cr)
        assert "800" in out
        assert "$0.001000" in out
        assert "Per-Node Breakdown" not in out

    def test_full_report(self) -> None:
        """Full report with per-node breakdown table."""
        cr = CostReport(
            session_id="s2",
            total_input_tokens=1000,
            total_output_tokens=500,
            total_tokens=1500,
            total_estimated_cost_usd=0.005,
            per_node=[
                NodeCost(
                    node_name="draft_update",
                    llm_model="gpt-4o",
                    input_tokens=800,
                    output_tokens=400,
                    total_tokens=1200,
                    estimated_cost_usd=0.004,
                    latency_ms=1200,
                ),
            ],
            models_used=["gpt-4o", "claude-3-5-sonnet"],
        )
        out = format_cost_md(cr)
        assert "1,500" in out
        assert "draft_update" in out
        assert "1200" in out
        assert "Per-Node Breakdown" in out


class TestSectionMd:
    """_section_md — renders a single PostmortemSection."""

    def test_none_section_returns_empty_list(self) -> None:
        """None -> []."""
        assert _section_md(None, "Test") == []

    def test_ai_generated_section(self) -> None:
        """AI-generated section has [AI-GENERATED] tag."""
        section = {"title": "Summary", "content": "Incident overview", "ai_generated": True}
        lines = _section_md(section, "Summary")
        assert "AI-GENERATED" in lines[0]
        assert "Incident overview" in lines[1]

    def test_not_ai_generated(self) -> None:
        """Non-AI section has [From session data] tag."""
        section = {"title": "Timeline", "content": "Events", "ai_generated": False}
        lines = _section_md(section, "Timeline")
        assert "From session data" in lines[0]
        assert "Events" in lines[1]
