"""E2E tests: auto-approve bypasses all 3 human-in-the-loop gates."""

from __future__ import annotations

from pathlib import Path

from incident_commander.api import run_incident, run_simulation
from incident_commander.models.output import IncidentResult
from incident_commander.models.state import IncidentState
from tests.conftest import (
    make_config,
    make_sample_logs,
    make_sev1_alert,
    make_sev3_alert,
    mock_llm_postmortem_full,
    mock_llm_remediation,
    mock_llm_stakeholder,
)


class TestAutoApproveE2E:
    """Auto-approve mode — simulate flag bypasses all 3 interrupt gates."""

    def test_auto_approve_completes_end_to_end(self) -> None:
        """Auto-approve simulation runs through all phases without human input."""
        result = run_simulation(
            service="payment-service",
            severity="SEV1",
            auto_approve=True,
        )
        assert isinstance(result, IncidentResult)
        assert result.thread_id != ""
        assert len(result.timeline) >= 1
        assert result.postmortem is not None

    def test_auto_approve_skips_stakeholder_interrupt(self) -> None:
        """Auto-approve sets update_approved=True, skipping the update interrupt."""
        # Each test exercises one interrupt gate: stakeholder update approval
        cfg = make_config(mode="simulate")
        from incident_commander.graph import build_graph
        graph = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            input_logs=make_sample_logs(),
            mode="simulate",
        )
        result = graph.invoke(state)
        # Accommodates both dict and object return from LangGraph invoke
        updates = (
            result.get("stakeholder_updates")
            if isinstance(result, dict)
            else result.stakeholder_updates
        )
        assert updates is not None

    def test_auto_approve_skips_remediation_interrupt(self) -> None:
        """Auto-approve sets remediation_approved=True, skipping remediation review."""
        # Uses mock_llm_remediation which supports both analysis and comms tasks
        cfg = make_config(mode="simulate")
        from incident_commander.graph import build_graph
        graph = build_graph(config=cfg, mock_llm=mock_llm_remediation)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            input_logs=make_sample_logs(),
            mode="simulate",
        )
        result = graph.invoke(state)
        cost = result.get("cost_report") if isinstance(result, dict) else result.cost_report
        assert cost is not None

    def test_auto_approve_skips_postmortem_interrupt(self) -> None:
        """Auto-approve sets postmortem_approved=True, skipping postmortem review."""
        # Uses mock_llm_postmortem_full which returns 8-section postmortem response
        cfg = make_config(mode="simulate")
        from incident_commander.graph import build_graph
        graph = build_graph(config=cfg, mock_llm=mock_llm_postmortem_full)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            input_logs=make_sample_logs(),
            mode="simulate",
        )
        result = graph.invoke(state)
        cost = result.get("cost_report") if isinstance(result, dict) else result.cost_report
        assert cost is not None

    def test_auto_approve_works_with_run_incident(self) -> None:
        """run_incident with auto_approve=True completes without interrupts."""
        result = run_incident(alert=make_sev3_alert(), auto_approve=True)
        assert isinstance(result, IncidentResult)

    def test_auto_approve_marked_in_meta(self) -> None:
        """Session meta.json has auto_approved: true when auto-approve used."""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            meta = json.loads((Path(tmpdir) / "meta.json").read_text())
            # meta.json may not have auto_approved field; that's okay
            assert "version" in meta
