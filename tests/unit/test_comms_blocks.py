"""Tests for comms_blocks output formatting."""

from __future__ import annotations

from incident_commander.api import run_simulation
from incident_commander.models.output import IncidentResult
from incident_commander.output.comms_blocks import format_comms_blocks_md


class TestFormatCommsBlocksMD:
    """format_comms_blocks_md output formatting."""

    def test_with_deploy_correlation(self) -> None:
        """Real simulation output optionally includes deploy correlation."""
        result = run_simulation(auto_approve=True)
        output = format_comms_blocks_md(result)
        if result.deploy_correlations:
            assert "Deploy Correlation" in output
            assert "PR #" in output
        else:
            assert "Deploy Correlation" not in output

    def test_with_remediation_suggestion(self) -> None:
        """Real simulation output includes remediation summary."""
        result = run_simulation(auto_approve=True)
        output = format_comms_blocks_md(result)
        assert "Remediation" in output

    def test_no_updates(self) -> None:
        """Empty stakeholder_updates shows 'No updates drafted'."""
        result = IncidentResult(
            thread_id="test-no-updates",
            timeline=[],
            stakeholder_updates=[],
            remediation_suggestions=[],
            deploy_correlations=[],
        )
        output = format_comms_blocks_md(result)
        assert "No updates drafted" in output
