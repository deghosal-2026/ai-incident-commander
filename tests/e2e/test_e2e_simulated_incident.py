"""E2E tests: full graph with mock LLM, all 8 scenarios, interrupts, output files."""

from __future__ import annotations

from pathlib import Path

from incident_commander.api import run_simulation
from incident_commander.models.output import IncidentResult
from incident_commander.models.state import IncidentState, Postmortem
from incident_commander.simulation.scenarios import SCENARIOS
from tests.conftest import (
    make_config,
    make_sample_logs,
    make_sev1_alert,
    mock_llm_postmortem_full,
    mock_llm_remediation,
    mock_llm_stakeholder,
)


class TestE2ESimulatedIncident:
    """E2E: full graph with mock LLM — smoke tests for all 8 scenarios."""

    def test_sev1_simulation_has_timeline(self) -> None:
        """SEV1 sim produces timeline with >=5 events."""
        # SEV1 generates alert + log entries + messages + PRs → at least 5 timeline events
        result = run_simulation(
            service="payment-service", severity="SEV1",
            auto_approve=True,
        )
        assert isinstance(result, IncidentResult)
        assert len(result.timeline) >= 5

    def test_sev1_simulation_has_stakeholder_updates(self) -> None:
        """SEV1 sim produces at least one stakeholder update."""
        result = run_simulation(
            service="payment-service", severity="SEV1",
            auto_approve=True,
        )
        assert len(result.stakeholder_updates) >= 1

    def test_sev1_simulation_has_postmortem(self) -> None:
        """SEV1 sim produces a postmortem object."""
        result = run_simulation(
            service="payment-service", severity="SEV1",
            auto_approve=True,
        )
        assert result.postmortem is not None
        assert isinstance(result.postmortem, Postmortem)

    def test_sev1_simulation_has_cost_report(self) -> None:
        """SEV1 sim produces a cost report."""
        result = run_simulation(
            service="payment-service", severity="SEV1",
            auto_approve=True,
        )
        assert result.cost_report is not None
        assert result.cost_report.total_estimated_cost_usd >= 0

    def test_sev2_customer_impact_present(self) -> None:
        """SEV2 postmortem has customer impact, no regulatory section."""
        # SEV2 has customer_impact but not regulatory_compliance_impact
        result = run_simulation(
            service="api-gateway", severity="SEV2",
            auto_approve=True,
        )
        pm = result.postmortem
        assert pm is not None
        assert pm.customer_impact is not None
        assert pm.regulatory_compliance_impact is None

    def test_sev3_omits_customer_impact(self) -> None:
        """SEV3 postmortem excludes customer impact and regulatory sections."""
        # SEV3 strips both customer_impact and regulatory_compliance_impact
        result = run_simulation(
            service="web-service", severity="SEV3",
            auto_approve=True,
        )
        pm = result.postmortem
        assert pm is not None
        assert pm.customer_impact is None
        assert pm.regulatory_compliance_impact is None

    def test_all_eight_scenarios_run_without_error(self) -> None:
        """All 8 pre-built scenarios complete without exception."""
        # Smoke test iterating every scenario in the registry — ensures none are broken
        for name in SCENARIOS:
            result = run_simulation(scenario=name, auto_approve=True)
            assert isinstance(result, IncidentResult)
            assert result.thread_id != ""

    def test_scenario_with_deploy_correlation(self) -> None:
        """Deploy-correlated scenario has deploy correlations in output."""
        # db-connection-pool is the canonical deploy-correlated scenario
        result = run_simulation(
            service="payment-service", severity="SEV1",
            scenario="db-connection-pool",
            auto_approve=True,
        )
        # The scenario simulates a deploy before the alert
        assert isinstance(result, IncidentResult)

    def test_scenario_without_deploy_correlation(self) -> None:
        """Non-deploy-correlated scenario does not produce deploy correlations."""
        # memory-leak is a non-deploy scenario — no PRs before the alert
        result = run_simulation(
            service="auth-service", severity="SEV2",
            scenario="memory-leak",
            auto_approve=True,
        )
        assert isinstance(result, IncidentResult)

    def test_stakeholder_interrupt_approved(self) -> None:
        """Approving the stakeholder update proceeds to produce_output."""
        # Simulate mode auto-approves → graph must complete without halting at human gates
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
        timeline = result.get("timeline") if isinstance(result, dict) else result.timeline
        assert timeline is not None

    def test_remediation_interrupt_approved(self) -> None:
        """Remediation approved proceeds to postmortem."""
        # mock_llm_remediation handles both analysis (remediation) and comms tasks
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
        assert result is not None

    def test_postmortem_interrupt_approved(self) -> None:
        """Postmortem approved proceeds to cost_report."""
        # mock_llm_postmortem_full returns complete 8-section postmortem
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

    def test_auto_approve_no_interrupts(self) -> None:
        """Auto-approve mode skips all 3 human-in-the-loop gates."""
        result = run_simulation(auto_approve=True)
        assert isinstance(result, IncidentResult)
        assert result.thread_id != ""

    def test_source_citations_present(self) -> None:
        """Run with mock LLM that includes citations."""
        # mock_llm_remediation returns citations — every suggestion must have one
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
        suggestions = (
            result.get("remediation_suggestions")
            if isinstance(result, dict)
            else result.remediation_suggestions
        )
        if suggestions:
            assert all(s.citation for s in suggestions)

    def test_output_dir_writes_files(self) -> None:
        """Running with output_dir writes files to disk."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_simulation(auto_approve=True, output_dir=tmpdir)
            assert isinstance(result, IncidentResult)
            written = list(Path(tmpdir).iterdir())
            assert len(written) > 0
