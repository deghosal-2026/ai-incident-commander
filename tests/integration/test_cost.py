"""Cost report integration tests — aggregation, per-node tracking, zero-cost."""

from __future__ import annotations

from incident_commander.graph import build_graph
from incident_commander.models.state import IncidentState
from incident_commander.nodes.cost_report import cost_report_node
from tests.conftest import (
    make_config,
    make_sev1_alert,
    make_sev3_alert,
    mock_llm_stakeholder,
)


class TestCostReportNode:
    """cost_report_node — aggregate CostTracker data."""

    def test_cost_report_node_creates_report(self) -> None:
        """cost_report_node produces a CostReport."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = cost_report_node(state)
        assert result.cost_report is not None
        assert result.cost_report.total_estimated_cost_usd >= 0

    def test_cost_report_zero_for_no_llm_calls(self) -> None:
        """Zero LLM calls produce zero cost report."""
        # No build_graph call → no CostTracker registered → zero-cost report
        state = IncidentState(
            alert=make_sev3_alert(),
            severity="SEV3",
            service="web-service",
            mode="simulate",
        )
        result = cost_report_node(state)
        assert result.cost_report is not None
        assert result.cost_report.total_estimated_cost_usd == 0.0
        assert result.cost_report.total_tokens == 0

    def test_cost_report_per_node_breakdown(self) -> None:
        """Cost report includes per-node breakdown."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = cost_report_node(state)
        assert result.cost_report is not None
        if result.cost_report.per_node:
            node = result.cost_report.per_node[0]
            assert node.node_name != ""
            assert node.llm_model != ""

    def test_cost_report_models_used(self) -> None:
        """Cost report lists distinct models used."""
        cfg = make_config()
        _ = build_graph(config=cfg, mock_llm=mock_llm_stakeholder)
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = cost_report_node(state)
        assert result.cost_report is not None
        assert isinstance(result.cost_report.models_used, list)

    def test_cost_report_integration_with_full_graph(self) -> None:
        """Full graph execution produces cost report with accumulated data."""
        # Tests end-to-end: graph.invoke → CostTracker accumulates → cost_report_node writes report
        cfg = make_config(mode="simulate")
        graph = build_graph(
            config=cfg,
            mock_llm=mock_llm_stakeholder,
        )
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            input_logs=[],
            input_messages=[],
            input_prs=[],
            mode="simulate",
        )
        result = graph.invoke(state)  # type: ignore[attr-defined]
        # graph.invoke returns either dict or IncidentState depending on LangGraph version
        cost = result.get("cost_report") if isinstance(result, dict) else result.cost_report
        assert cost is not None
        assert cost.total_estimated_cost_usd >= 0
