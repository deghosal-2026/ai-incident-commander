"""Postmortem integration tests — generation, severity sections, blameless rules."""

from __future__ import annotations

from typing import Any

from incident_commander.graph import build_graph
from incident_commander.models.state import IncidentState
from incident_commander.nodes.postmortem import (
    generate_postmortem_node,
    interrupt_for_postmortem_review,
)
from tests.conftest import (
    make_config,
    make_sev1_alert,
    make_sev3_alert,
    mock_llm_postmortem_full,
    mock_llm_postmortem_minimal,
)


class TestGeneratePostmortemNode:
    """generate_postmortem_node — COE-format postmortem generation."""

    def test_sev1_all_sections(self) -> None:
        """SEV1 produces all 8 sections."""
        # mock_llm_postmortem_full returns all 8 sections → SEV1 routing must preserve them all
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_postmortem_full)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            incident_id=alert.incident_id,
            timeline=[],
            mode="simulate",
        )
        result = generate_postmortem_node(state)
        assert result.postmortem is not None
        assert result.postmortem.summary is not None
        assert result.postmortem.customer_impact is not None
        assert result.postmortem.timeline is not None
        assert result.postmortem.root_cause_analysis is not None
        assert result.postmortem.systemic_contributing_factors is not None
        assert len(result.postmortem.action_items) > 0
        assert result.postmortem.stakeholder_communication_log is not None
        assert result.postmortem.regulatory_compliance_impact is not None

    def test_sev3_omits_optional_sections(self) -> None:
        """SEV3 produces 5 sections (no customer_impact, regulatory, comm log)."""
        # SEV3 routing strips customer_impact, regulatory, and comm log — must be None
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_postmortem_minimal)
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            incident_id=alert.incident_id,
            timeline=[],
            mode="simulate",
        )
        result = generate_postmortem_node(state)
        assert result.postmortem is not None
        assert result.postmortem.summary is not None
        assert result.postmortem.customer_impact is None
        assert result.postmortem.timeline is not None
        assert result.postmortem.root_cause_analysis is not None
        assert result.postmortem.systemic_contributing_factors is not None
        assert len(result.postmortem.action_items) > 0
        assert result.postmortem.stakeholder_communication_log is None
        assert result.postmortem.regulatory_compliance_impact is None

    def test_empty_timeline_handled(self) -> None:
        """Empty timeline does not crash postmortem generation."""
        # No timeline events — generate_postmortem_node must not crash on empty input
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_postmortem_full)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = generate_postmortem_node(state)
        assert result.postmortem is not None

    def test_llm_failure_in_postmortem(self) -> None:
        """LLM failure produces postmortem with fallback text without crashing."""
        def failing_mock(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
            if task == "postmortem":
                raise RuntimeError("LLM timeout")
            return ("ok", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})

        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=failing_mock)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            incident_id=alert.incident_id,
            timeline=[],
            mode="simulate",
        )
        result = generate_postmortem_node(state)
        assert result.postmortem is not None
        assert "insufficient data" in result.postmortem.summary.content

    def test_sev2_postmortem_sections(self) -> None:
        """SEV2 postmortem has customer_impact but not regulatory or comm log."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_postmortem_full)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity="SEV2",
            service=alert.service,
            incident_id=alert.incident_id,
            timeline=[],
            mode="simulate",
        )
        result = generate_postmortem_node(state)
        assert result.postmortem is not None
        assert result.postmortem.summary is not None
        assert result.postmortem.customer_impact is not None
        assert result.postmortem.regulatory_compliance_impact is None
        assert result.postmortem.stakeholder_communication_log is None

    def test_mttr_calculated(self) -> None:
        """MTTR calculated from resolved_at - alert.timestamp."""
        # Mean Time To Resolve: computed as integer minutes between alert time and resolution
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_postmortem_full)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = generate_postmortem_node(state)
        assert result.postmortem is not None
        if result.postmortem.resolved_at and alert.timestamp:
            diff = (result.postmortem.resolved_at - alert.timestamp).total_seconds()
            expected = int(diff / 60)
            assert result.postmortem.mttr_minutes == expected


class TestPostmortemParse:
    """Postmortem response parsing for section counts and action items."""

    def test_mock_full_postmortem_has_all_sections(self) -> None:
        """Full mock response produces postmortem with 8 sections."""
        prompt = "test"
        response, _info = mock_llm_postmortem_full(prompt, "postmortem")
        assert "SUMMARY" in response
        assert "CUSTOMER_IMPACT" in response
        assert "TIMELINE" in response
        assert "ROOT_CAUSE_ANALYSIS" in response
        assert "ACTION_ITEMS" in response

    def test_mock_minimal_postmortem_no_optional_sections(self) -> None:
        """Minimal mock response omits optional sections."""
        prompt = "test"
        response, _info = mock_llm_postmortem_minimal(prompt, "postmortem")
        assert "SUMMARY" in response
        assert "CUSTOMER_IMPACT" not in response


class TestInterruptForPostmortemReview:
    """interrupt_for_postmortem_review — auto-approves in simulate mode."""

    def test_simulate_auto_approves(self) -> None:
        """Simulate mode auto-approves postmortem."""
        cfg = make_config(mode="simulate")
        _ = build_graph(config=cfg, mock_llm=mock_llm_postmortem_full)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        state = generate_postmortem_node(state)
        result = interrupt_for_postmortem_review(state)
        assert result.postmortem_approved is True
        assert result.postmortem is not None
        assert result.postmortem.approved is True

    def test_run_mode_no_auto_approve(self) -> None:
        """Run mode does not auto-approve postmortem."""
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="run",
        )
        result = interrupt_for_postmortem_review(state)
        assert result.postmortem_approved is False
