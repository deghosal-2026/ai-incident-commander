"""API integration tests — run_incident, run_simulation, output writing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from incident_commander.api import run_incident, run_simulation
from incident_commander.config import Config as AppConfig
from incident_commander.config import LLMConfig
from incident_commander.models.input import Runbook
from incident_commander.models.output import IncidentResult
from incident_commander.models.state import Alert, TimelineEvent
from tests.conftest import (
    NOW,
    make_sample_logs,
    make_sample_messages,
    make_sample_prs,
)


class TestRunIncident:
    """run_incident — accepts all input forms and returns IncidentResult."""

    def test_run_incident_with_alert_object(self) -> None:
        """run_incident with Alert object returns IncidentResult."""
        # Minimum viable call: just an alert, no logs/messages/PRs
        alert = Alert(
            severity="SEV3",
            service="test-service",
            summary="Test alert",
            source="test",
            timestamp=NOW,
        )
        result = run_incident(alert=alert, auto_approve=True)
        assert isinstance(result, IncidentResult)
        assert result.thread_id != ""
        assert result.timeline is not None

    def test_run_incident_with_logs(self) -> None:
        """run_incident accepts log entries."""
        # Adding logs feeds the timeline builder for richer output
        alert = Alert(
            severity="SEV3",
            service="test-service",
            summary="Log test",
            source="test",
            timestamp=NOW,
        )
        result = run_incident(
            alert=alert,
            logs=make_sample_logs(),
            auto_approve=True,
        )
        assert isinstance(result, IncidentResult)

    def test_run_incident_with_all_inputs(self) -> None:
        """run_incident accepts all optional input channels."""
        # Tests that logs + messages + PRs all flow through the graph correctly
        alert = Alert(
            severity="SEV3",
            service="test-service",
            summary="Full input test",
            source="test",
            timestamp=NOW,
        )
        result = run_incident(
            alert=alert,
            logs=make_sample_logs(),
            messages=make_sample_messages(),
            github=make_sample_prs(),
            auto_approve=True,
        )
        assert isinstance(result, IncidentResult)

    def test_run_incident_with_thread_id(self) -> None:
        """run_incident preserves thread_id across runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert = Alert(
                severity="SEV3",
                service="test-service",
                summary="Thread ID test",
                source="test",
                timestamp=NOW,
            )
            result1 = run_incident(alert=alert, output_dir=tmpdir, auto_approve=True)
            captured_id = result1.thread_id
            assert captured_id != ""

            result2 = run_incident(
                alert=alert,
                output_dir=tmpdir,
                auto_approve=True,
                thread_id=captured_id,
            )
            # TODO: thread_id resume not implemented
            assert result2.thread_id == captured_id

    def test_run_incident_with_manual_events(self) -> None:
        """run_incident accepts manual timeline events."""
        alert = Alert(
            severity="SEV3",
            service="test-service",
            summary="Manual events test",
            source="test",
            timestamp=NOW,
        )
        manual_events = [
            TimelineEvent(
                timestamp=NOW,
                source="manual",
                event_type="manual",
                content="test",
                trust_level="low",
            )
        ]
        result = run_incident(
            alert=alert,
            manual_events=manual_events,
            auto_approve=True,
        )
        matching = [
            e
            for e in result.timeline
            if e.source == "manual" and e.trust_level == "low"
        ]
        assert len(matching) > 0

    def test_run_incident_with_runbooks(self) -> None:
        """run_incident accepts runbooks without crashing."""
        alert = Alert(
            severity="SEV3",
            service="test-service",
            summary="Runbooks test",
            source="test",
            timestamp=NOW,
        )
        runbooks = [
            Runbook(
                id="rb-1",
                title="test",
                path="/test",
                content="test content",
                keywords=["test"],
                service="*",
            )
        ]
        result = run_incident(alert=alert, runbooks=runbooks, auto_approve=True)
        assert result is not None

    @pytest.mark.xfail(reason="output_format='json' not implemented — always writes markdown")
    def test_output_format_json(self) -> None:
        """output_format='json' does not produce .md files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AppConfig(output_format="json")
            alert = Alert(
                severity="SEV3",
                service="test-service",
                summary="JSON output test",
                source="test",
                timestamp=NOW,
            )
            run_incident(
                alert=alert,
                output_dir=tmpdir,
                config=cfg,
                auto_approve=True,
            )
            md_files = [p for p in Path(tmpdir).iterdir() if p.suffix == ".md"]
            # TODO: output_format="json" not implemented — MarkdownOutputWriter always writes .md
            assert len(md_files) == 0

    def test_run_incident_with_output_dir(self) -> None:
        """run_incident creates output files when output_dir is set."""
        # output_dir triggers file writing — at least one file must be created
        with tempfile.TemporaryDirectory() as tmpdir:
            alert = Alert(
                severity="SEV3",
                service="test-service",
                summary="Output test",
                source="test",
                timestamp=NOW,
            )
            result = run_incident(
                alert=alert,
                output_dir=tmpdir,
                auto_approve=True,
            )
            assert isinstance(result, IncidentResult)
            paths = list(Path(tmpdir).iterdir())
            assert len(paths) > 0


class TestRunSimulation:
    """run_simulation — bundled simulation scenarios."""

    def test_run_simulation_default(self) -> None:
        """run_simulation with defaults returns IncidentResult."""
        # Default simulation (payment-service, SEV1) must complete without config
        result = run_simulation(auto_approve=True)
        assert isinstance(result, IncidentResult)
        assert result.thread_id != ""

    def test_run_simulation_custom_service(self) -> None:
        """run_simulation with custom service returns IncidentResult."""
        # Verifies non-default service + severity combinations work
        result = run_simulation(
            service="api-gateway",
            severity="SEV2",
            auto_approve=True,
        )
        assert isinstance(result, IncidentResult)

    def test_run_simulation_with_output_dir(self) -> None:
        """run_simulation writes output to directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_simulation(
                auto_approve=True,
                output_dir=tmpdir,
            )
            assert isinstance(result, IncidentResult)
            paths = list(Path(tmpdir).iterdir())
            assert len(paths) > 0

    def test_run_simulation_with_custom_llm_config(self) -> None:
        """run_simulation accepts custom LLMConfig."""
        cfg = AppConfig(llm=LLMConfig(comms_model="gpt-4o-mini"))
        result = run_simulation(config=cfg, auto_approve=True)
        assert result is not None
        assert result.cost_report is not None
        assert "gpt-4o-mini" in result.cost_report.models_used

    def test_run_simulation_return_type(self) -> None:
        """run_simulation returns object with all expected fields."""
        # Verify output has proper types for each major section
        result = run_simulation(auto_approve=True)
        assert result.thread_id != ""
        assert isinstance(result.timeline, list)
        assert isinstance(result.stakeholder_updates, list)
        assert isinstance(result.remediation_suggestions, list)
        assert isinstance(result.deploy_correlations, list)
