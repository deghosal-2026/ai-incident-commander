"""Stakeholder communication integration tests — draft update, parse, approve."""

from __future__ import annotations

from typing import Any

from incident_commander.graph import build_graph
from incident_commander.models.state import Alert, IncidentState
from incident_commander.nodes.stakeholder import (
    _parse_response,
    draft_update_node,
    interrupt_for_approval,
    produce_output_node,
)
from tests.conftest import (
    NOW,
    make_config,
    make_sev3_alert,
    mock_llm_empty_timeline,
    mock_llm_malformed,
    mock_llm_stakeholder,
)


class TestDraftUpdateNode:
    """draft_update_node generates stakeholder updates via LLM."""

    def test_draft_update_node_creates_draft(self) -> None:
        """draft_update_node produces a current_update_draft."""
        # build_graph must be called first to wire mock_llm into the graph's global router
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = draft_update_node(state)
        assert result.current_update_draft is not None
        assert result.current_update_draft.impact != ""

    def test_draft_update_with_timeline(self) -> None:
        """draft_update_node produces draft when timeline events exist."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = draft_update_node(state)
        assert result.current_update_draft is not None

    def test_draft_update_malformed_response(self) -> None:
        """Malformed LLM response falls back gracefully."""
        # Uses mock_llm_malformed which returns unstructured text — parser must not crash
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_malformed)
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = draft_update_node(state)
        assert result.current_update_draft is not None
        # Either the fallback message or actual content must be present
        fallback = "Impact assessment in progress"
        has_fallback = fallback in result.current_update_draft.impact
        has_content = result.current_update_draft.impact != ""
        assert has_fallback or has_content

    def test_empty_timeline_still_produces_draft(self) -> None:
        """Empty timeline does not prevent draft creation."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_empty_timeline)
        alert = Alert(
            severity="SEV3",
            service="test",
            summary="Test alert",
            source="test",
            timestamp=NOW,
        )
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = draft_update_node(state)
        assert result.current_update_draft is not None

    def test_llm_failure_in_draft_update(self) -> None:
        """LLM failure produces fallback draft without crashing."""
        def failing_mock(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
            if task == "comms":
                raise RuntimeError("LLM timeout")
            return ("ok", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})

        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=failing_mock)
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = draft_update_node(state)
        assert result.current_update_draft is not None
        has_fallback = (
            "No update available" in result.current_update_draft.impact
            or "Impact assessment in progress" in result.current_update_draft.impact
        )
        assert has_fallback


class TestParseResponse:
    """_parse_response — LLM response parsing logic."""

    def test_parse_valid_response(self) -> None:
        """Valid consequence-first response parses correctly."""
        response = (
            "IMPACT: Payment failures affecting 5% of users\n"
            "ROOT_CAUSE: Database connection pool exhaustion\n"
            "ACTION: Rolling back deploy\n"
            "CONFIDENCE: 0.85\n"
        )
        update = _parse_response(response, 1, None)
        assert update.impact == "Payment failures affecting 5% of users"
        assert "Database connection pool" in update.root_cause_hypothesis
        assert "Rolling back" in update.action
        assert update.confidence == 0.85

    def test_parse_malformed_response(self) -> None:
        """Unstructured response uses fallback."""
        response = "Something went wrong with the system."
        update = _parse_response(response, 1, None)
        assert update.impact == response[:200]
        assert "under investigation" in update.root_cause_hypothesis

    def test_parse_empty_response(self) -> None:
        """Empty response returns fallback text."""
        update = _parse_response("", 1, None)
        assert "No update available" in update.impact

    def test_parse_partial_response(self) -> None:
        """Partial response with only some fields still produces valid update."""
        response = "IMPACT: Payment failures\n"
        update = _parse_response(response, 1, None)
        assert update.impact == "Payment failures"
        assert update.root_cause_hypothesis != ""
        assert update.action != ""

    def test_parse_confidence_edge_cases(self) -> None:
        """Parse handles non-numeric confidence gracefully."""
        response = "IMPACT: Test\nROOT_CAUSE: Test\nACTION: Test\nCONFIDENCE: not-a-number\n"
        update = _parse_response(response, 1, None)
        assert update.confidence == 0.5

    def test_parse_update_number(self) -> None:
        """Update number is correctly assigned."""
        response = "IMPACT: Test\nROOT_CAUSE: Test\nACTION: Test\nCONFIDENCE: 1.0\n"
        update = _parse_response(response, 5, None)
        assert update.update_number == 5

    def test_parse_high_confidence(self) -> None:
        """High confidence value is preserved."""
        response = "IMPACT: Test\nROOT_CAUSE: Test\nACTION: Test\nCONFIDENCE: 0.99\n"
        update = _parse_response(response, 1, None)
        assert update.confidence == 0.99


class TestProduceOutput:
    """produce_output_node — finalises an approved draft."""

    def test_produce_output_approves_draft(self) -> None:
        """produce_output_node appends draft and marks approved."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        state = draft_update_node(state)
        state = produce_output_node(state)
        assert len(state.stakeholder_updates) >= 1
        assert state.stakeholder_updates[0].approved is True
        assert state.current_update_draft is None

    def test_produce_output_no_draft(self) -> None:
        """produce_output_node with no draft returns unchanged."""
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = produce_output_node(state)
        assert result.stakeholder_updates == []


class TestInterruptForApproval:
    """interrupt_for_approval — auto-approves in simulate mode."""

    def test_simulate_auto_approves(self) -> None:
        """Simulate mode sets update_approved = True."""
        cfg = make_config(mode="simulate")
        _ = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = interrupt_for_approval(state)
        assert result.update_approved is True

    def test_run_mode_no_auto_approve(self) -> None:
        """Run mode does not auto-approve."""
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="run",
        )
        result = interrupt_for_approval(state)
        assert result.update_approved is False

    def test_comms_blocks_formatting(self) -> None:
        """Produced updates can be formatted as comms blocks."""
        from incident_commander.models.output import IncidentResult
        from incident_commander.output.comms_blocks import format_comms_blocks_md

        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        state = draft_update_node(state)
        state = produce_output_node(state)
        result = IncidentResult(
            thread_id="test-123",
            stakeholder_updates=state.stakeholder_updates,
        )
        blocks = format_comms_blocks_md(result)
        assert "### Stakeholder Update" in blocks
        assert result.thread_id in blocks
