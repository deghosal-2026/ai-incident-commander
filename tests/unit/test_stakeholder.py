"""Tests for stakeholder module: _build_prompt, _parse_response."""

from __future__ import annotations

from incident_commander.models.state import DeployCorrelation, IncidentState
from incident_commander.nodes.stakeholder import _build_prompt, _parse_response
from tests.conftest import NOW


class TestBuildPrompt:
    """_build_prompt — constructs LLM prompt for stakeholder updates."""

    def test_with_deploy_correlations(self) -> None:
        """Deploy correlation info included when deploy_correlations is present."""
        state = IncidentState(
            severity="SEV1",
            service="payment-service",
            deploy_correlations=[
                DeployCorrelation(
                    pr_number=42,
                    pr_title="Fix DB pool settings",
                    author="bob",
                    merge_time=NOW,
                    minutes_before_alert=5,
                    correlation_strength="strong",
                ),
            ],
        )
        prompt = _build_prompt(state)
        assert "Deploy correlations" in prompt
        assert "PR #42" in prompt
        assert "Fix DB pool settings" in prompt

    def test_with_retrieved_runbooks(self) -> None:
        """Runbook titles included when retrieved_runbooks is present."""
        state = IncidentState(
            severity="SEV1",
            service="payment-service",
            retrieved_runbooks=[
                {"title": "DB Pool Tuning", "relevance_score": 0.95},
            ],
        )
        prompt = _build_prompt(state)
        assert "Relevant runbooks" in prompt
        assert "DB Pool Tuning" in prompt

    def test_without_deploy_correlations_or_runbooks(self) -> None:
        """Prompt still works without deploy correlations or runbooks."""
        state = IncidentState(
            severity="SEV2",
            service="web-service",
        )
        prompt = _build_prompt(state)
        assert "SEV2" in prompt
        assert "web-service" in prompt
        assert "Deploy correlations" not in prompt
        assert "Relevant runbooks" not in prompt

    def test_includes_timeline_and_format_instructions(self) -> None:
        """Prompt includes timeline summary and expected response format."""
        state = IncidentState(severity="SEV3", service="srv")
        prompt = _build_prompt(state)
        assert "IMPACT:" in prompt
        assert "ROOT_CAUSE:" in prompt
        assert "ACTION:" in prompt
        assert "CONFIDENCE:" in prompt


class TestParseResponse:
    """_parse_response — parses LLM output into StakeholderUpdate."""

    def test_empty_response_uses_fallback(self) -> None:
        """Empty string response falls back to 'No update available'."""
        update = _parse_response("", 1, None)
        assert "No update available" in update.impact
        assert "Root cause under investigation" in update.root_cause_hypothesis
        assert "Investigating" in update.action
        assert update.update_number == 1

    def test_parsed_response_populates_fields(self) -> None:
        """Properly formatted response fills all fields."""
        text = (
            "IMPACT: Payment failures affecting 5% of users\n"
            "ROOT_CAUSE: DB pool exhaustion\n"
            "ACTION: Rolling back deploy\n"
            "CONFIDENCE: 0.85\n"
        )
        update = _parse_response(text, 2, NOW)
        assert update.impact == "Payment failures affecting 5% of users"
        assert update.root_cause_hypothesis == "DB pool exhaustion"
        assert update.action == "Rolling back deploy"
        assert update.confidence == 0.85
        assert update.update_number == 2
