"""Tests for the remediation module: helpers and suggest_remediation_node."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import incident_commander.nodes.remediation as rem
from incident_commander.config import Config
from incident_commander.models.state import (
    Alert,
    DeployCorrelation,
    IncidentState,
    RemediationSuggestion,
)
from incident_commander.nodes.remediation import (
    _build_dry_run_prompt,
    _build_remediation_prompt,
    _get_threshold,
    init_config,
    suggest_remediation_node,
)


class TestBuildRemediationPrompt:
    """_build_remediation_prompt — constructs LLM prompt."""

    def test_with_deploy_correlations(self) -> None:
        """Prompt includes deploy correlation details."""
        state = IncidentState()
        state.service = "payment"
        state.alert = Alert(
            severity="SEV1", service="payment",
            summary="DB pool exhausted",
            timestamp=datetime.now(),
        )
        state.deploy_correlations = [
            DeployCorrelation(
                pr_number=42, pr_title="fix: increase pool",
                author="bob", merge_time=datetime.now(),
                minutes_before_alert=5,
            ),
        ]
        prompt = _build_remediation_prompt(state)
        assert "Deploy correlation: PR #42" in prompt


class TestBuildDryRunPrompt:
    """_build_dry_run_prompt — builds simulation prompt."""

    def test_with_none_remediation(self) -> None:
        """None remediation returns empty string."""
        state = IncidentState()
        state.current_remediation = None
        assert _build_dry_run_prompt(state) == ""


class TestGetThreshold:
    """_get_threshold — returns threshold from config or default."""

    def test_with_init_config(self) -> None:
        """init_config sets threshold to the configured value."""
        init_config(Config(confidence_threshold=0.8))
        assert _get_threshold() == 0.8

    def test_without_init_config(self) -> None:
        """Without init_config, default threshold is 0.7."""
        rem._config = None
        assert _get_threshold() == 0.7


class TestSimilarIncidentsCleanup:
    """suggest_remediation_node — similar_incidents cleanup."""

    @patch("incident_commander.nodes.remediation._parse_remediation_response")
    @patch("incident_commander.nodes.remediation.get_llm_router")
    def test_similar_incidents_none_cleaned_to_empty_list(
        self, mock_get_router: MagicMock, mock_parse: MagicMock,
    ) -> None:
        """similar_incidents=None with non-empty citation is cleaned to []."""
        mock_get_router.return_value = MagicMock()
        mock_get_router.return_value.generate.return_value = ("ignored", {})

        suggestion = RemediationSuggestion.model_construct(
            action="Restart DB",
            citation="runbook/db.md",
            confidence=0.9,
            similar_incidents=None,
        )
        mock_parse.return_value = suggestion

        state = IncidentState()
        state.service = "srv"
        state.alert = Alert(
            severity="SEV1", service="srv",
            summary="test",
            timestamp=datetime.now(),
        )

        result = suggest_remediation_node(state)
        assert result.current_remediation is not None
        assert result.current_remediation.similar_incidents == []
        assert result.current_remediation.citation != ""
