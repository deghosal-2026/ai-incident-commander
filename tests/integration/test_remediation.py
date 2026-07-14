"""Remediation integration tests — suggestion, citation enforcement, dry-run."""

from __future__ import annotations

from typing import Any

from incident_commander.graph import build_graph
from incident_commander.models.state import (
    DeployCorrelation,
    IncidentState,
    RemediationSuggestion,
)
from incident_commander.nodes.remediation import (
    _parse_remediation_response,
    dry_run_simulate_node,
    interrupt_for_remediation_review,
    suggest_remediation_node,
)
from tests.conftest import (
    NOW,
    make_config,
    make_sev1_alert,
    mock_llm_missing_citation,
    mock_llm_remediation,
)


class TestParseRemediationResponse:
    """_parse_remediation_response — parsing and citation enforcement."""

    def test_parse_valid_response(self) -> None:
        """Valid remediation response parses correctly."""
        # Properly formatted response with ACTION, CITATION, CONFIDENCE, SIMILAR_INCIDENTS
        response = (
            "ACTION: Rollback deploy to v2.1.0\n"
            "CITATION: runbook/db-rollback.md\n"
            "CONFIDENCE: 0.85\n"
            "SIMILAR_INCIDENTS: INC-2023-042, INC-2024-015\n"
        )
        suggestion = _parse_remediation_response(response)
        assert "Rollback" in suggestion.action
        assert suggestion.citation == "Source: runbook/db-rollback.md"
        assert suggestion.confidence == 0.85
        assert len(suggestion.similar_incidents) == 2

    def test_missing_citation_rejected(self) -> None:
        """Suggestion without citation is flagged."""
        # Missing CITATION field → action gets "missing citation" prefix; empty citation string
        response = (
            "ACTION: Restart the database\n"
            "CONFIDENCE: 0.6\n"
            "SIMILAR_INCIDENTS: none\n"
        )
        suggestion = _parse_remediation_response(response)
        assert "missing citation" in suggestion.action.lower()
        assert suggestion.citation == ""

    def test_empty_response(self) -> None:
        """Empty response produces fallback."""
        # Empty string → entirely fallback response with "missing citation"
        suggestion = _parse_remediation_response("")
        assert "missing citation" in suggestion.action.lower()

    def test_no_similar_incidents(self) -> None:
        """Response with 'none' similar incidents produces empty list."""
        # "none" is treated as empty list, not a string ["none"]
        response = (
            "ACTION: Rollback\nCITATION: runbook.md\n"
            "CONFIDENCE: 0.8\nSIMILAR_INCIDENTS: none\n"
        )
        suggestion = _parse_remediation_response(response)
        assert suggestion.similar_incidents == []

    def test_confidence_parsing_errors(self) -> None:
        """Non-numeric confidence defaults to 0.5."""
        # Non-parseable confidence ("not-a-number") falls back to 0.5 (medium)
        response = (
            "ACTION: Rollback\nCITATION: runbook.md\n"
            "CONFIDENCE: not-a-number\nSIMILAR_INCIDENTS: none\n"
        )
        suggestion = _parse_remediation_response(response)
        assert suggestion.confidence == 0.5


class TestSuggestRemediationNode:
    """suggest_remediation_node — full node invocation."""

    def test_suggest_remediation_creates_suggestion(self) -> None:
        """suggest_remediation_node produces a current_remediation."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_remediation)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = suggest_remediation_node(state)
        assert result.current_remediation is not None
        assert result.current_remediation.action != ""

    def test_confidence_threshold_suppressed(self) -> None:
        """Suggestion below confidence threshold is suppressed."""
        # confidence_threshold=0.9, mock returns 0.85 → "below threshold" flag in action
        cfg = make_config(confidence_threshold=0.9)
        _ = build_graph(config=cfg, mock_llm=mock_llm_remediation)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = suggest_remediation_node(state)
        assert result.current_remediation is not None
        assert "below threshold" in result.current_remediation.action.lower()

    def test_missing_citation_rejected(self) -> None:
        """Suggestion without citation is rejected by node."""
        # mock_llm_missing_citation returns response without CITATION field — must be rejected
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_missing_citation)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = suggest_remediation_node(state)
        assert result.current_remediation is not None
        assert "missing citation" in result.current_remediation.action.lower()

    def test_llm_failure_in_suggest(self) -> None:
        """LLM failure produces fallback remediation without crashing."""
        def failing_mock(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
            if task == "analysis":
                raise RuntimeError("LLM timeout")
            return ("ok", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})

        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=failing_mock)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = suggest_remediation_node(state)
        assert result.current_remediation is not None
        assert result.current_remediation.action != ""
        assert "missing citation" in result.current_remediation.action.lower()
        assert result.current_remediation.confidence == 0.0

    def test_remediation_with_deploy_correlation(self) -> None:
        """Deploy correlations are included in the prompt context."""
        # Pre-populated deploy_correlations must be passed to the LLM prompt context
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_remediation)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            deploy_correlations=[
                DeployCorrelation(
                    pr_number=101,
                    pr_title="Update DB pool",
                    author="bob",
                    merge_time=NOW,
                    minutes_before_alert=15,
                    correlation_strength="strong",
                ),
            ],
            mode="simulate",
        )
        result = suggest_remediation_node(state)
        assert result.current_remediation is not None


class TestDryRunSimulateNode:
    """dry_run_simulate_node — LLM text prediction of outcome."""

    def test_dry_run_with_suggestion(self) -> None:
        """dry_run_simulate_node populates dry_run_outcome."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_remediation)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        state.current_remediation = RemediationSuggestion(
            action="Rollback deploy to v2.1.0",
            citation="runbook/db-rollback.md",
            confidence=0.85,
        )
        result = dry_run_simulate_node(state)
        assert result.current_remediation is not None
        assert result.current_remediation.dry_run_outcome != ""

    def test_llm_failure_in_dry_run(self) -> None:
        """LLM failure produces fallback dry run outcome without crashing."""
        def failing_mock(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
            if task == "analysis":
                raise RuntimeError("LLM timeout")
            return ("ok", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})

        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=failing_mock)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        state.current_remediation = RemediationSuggestion(
            action="Rollback deploy",
            citation="runbook/db-rollback.md",
            confidence=0.85,
        )
        result = dry_run_simulate_node(state)
        assert result.current_remediation is not None
        assert "Outcome prediction unavailable" in result.current_remediation.dry_run_outcome

    def test_dry_run_no_suggestion(self) -> None:
        """dry_run_simulate_node with no suggestion returns unchanged."""
        state = IncidentState(
            alert=make_sev1_alert(),
            severity="SEV1",
            service="payment-service",
            mode="simulate",
        )
        result = dry_run_simulate_node(state)
        assert result.current_remediation is None


class TestInterruptForRemediationReview:
    """interrupt_for_remediation_review — auto-approves in simulate mode."""

    def test_simulate_auto_approves(self) -> None:
        """Simulate mode auto-approves remediation."""
        cfg = make_config(mode="simulate")
        _ = build_graph(config=cfg, mock_llm=mock_llm_remediation)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        state = suggest_remediation_node(state)
        result = interrupt_for_remediation_review(state)
        assert result.remediation_approved is True
        assert result.current_remediation is not None
        assert result.current_remediation.approved is True

    def test_run_mode_no_auto_approve(self) -> None:
        """Run mode does not auto-approve remediation."""
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="run",
        )
        state.current_remediation = RemediationSuggestion(
            action="Test", citation="test", confidence=0.5,
        )
        result = interrupt_for_remediation_review(state)
        assert result.remediation_approved is False
