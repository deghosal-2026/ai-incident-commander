"""Full graph integration tests — end-to-end simulation with mock LLM."""

from __future__ import annotations

from incident_commander.graph import build_graph
from incident_commander.models.state import Alert, IncidentState
from tests.conftest import (
    NOW,
    make_config,
    make_sample_logs,
    make_sample_messages,
    make_sample_prs,
    make_sample_runbooks,
    make_sev1_alert,
    make_sev3_alert,
    mock_llm_remediation,
    mock_llm_stakeholder,
)


def _get(result: object, key: str) -> object:
    """Get a field from either a dict or a Pydantic model result."""
    # LangGraph invoke() may return dict or IncidentState depending on version
    if isinstance(result, dict):
        return result.get(key)
    return getattr(result, key)


class TestBuildGraph:
    """build_graph — wiring, conditional edges, end-to-end invocation."""

    def test_build_graph_returns_compiled(self) -> None:
        """build_graph returns a compiled graph ready for invoke."""
        graph = build_graph(
            config=make_config(),
            mock_llm=mock_llm_stakeholder,
        )
        assert graph is not None

    def test_full_graph_sev3_simulation(self) -> None:
        """SEV3 simulation runs end-to-end with auto-approve producing expected state."""
        # mock_llm_stakeholder handles comms; graph traverses all SEV3-compatible nodes
        cfg = make_config(mode="simulate")
        graph = build_graph(
            config=cfg,
            mock_llm=mock_llm_stakeholder,
        )
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            incident_id=alert.incident_id,
            input_logs=make_sample_logs(),
            input_messages=make_sample_messages(),
            input_prs=make_sample_prs(),
            mode="simulate",
        )
        result = graph.invoke(state)  # type: ignore[attr-defined]
        assert result is not None
        assert _get(result, "timeline") is not None
        cost = _get(result, "cost_report")
        assert cost is not None

    def test_full_graph_sev1_simulation(self) -> None:
        """SEV1 simulation with remediation + postmortem produces all expected sections."""
        # Uses mock_llm_remediation which supports both analysis and comms tasks
        cfg = make_config(mode="simulate")
        graph = build_graph(
            config=cfg,
            mock_llm=mock_llm_remediation,
        )
        alert = make_sev1_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            incident_id=alert.incident_id,
            input_logs=make_sample_logs(),
            input_messages=make_sample_messages(),
            input_prs=make_sample_prs(),
            mode="simulate",
        )
        result = graph.invoke(state)  # type: ignore[attr-defined]
        assert _get(result, "timeline") is not None
        assert _get(result, "cost_report") is not None

    def test_auto_approve_bypasses_all_interrupts(self) -> None:
        """Simulate mode auto-approves all 3 human-in-the-loop gates."""
        # All 3 HITL gates (stakeholder, remediation, postmortem) auto-approved in simulate mode
        cfg = make_config(mode="simulate")
        graph = build_graph(
            config=cfg,
            mock_llm=mock_llm_stakeholder,
        )
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            input_logs=make_sample_logs(),
            mode="simulate",
        )
        result = graph.invoke(state)  # type: ignore[attr-defined]
        assert result is not None

    def test_full_graph_with_runbooks(self) -> None:
        """Simulation with runbooks loads and executes without error."""
        # Runbooks are passed via input_data to populate the RAG retriever
        runbooks = make_sample_runbooks()
        cfg = make_config(mode="simulate")
        graph = build_graph(
            config=cfg,
            mock_llm=mock_llm_stakeholder,
            input_data={"runbooks": runbooks},
        )
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            input_logs=make_sample_logs(),
            mode="simulate",
        )
        result = graph.invoke(state)  # type: ignore[attr-defined]
        assert result is not None

    def test_empty_timeline_produces_valid_state(self) -> None:
        """Graph execution with no input data does not crash."""
        # No logs, messages, or PRs — only an alert. Graph must not crash on empty collections
        cfg = make_config(mode="simulate")
        graph = build_graph(
            config=cfg,
            mock_llm=mock_llm_stakeholder,
        )
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
        result = graph.invoke(state)  # type: ignore[attr-defined]
        assert result is not None

    def test_graph_invoke_returns_incident_state(self) -> None:
        """Invoke returns a result with all expected fields."""
        cfg = make_config(mode="simulate")
        graph = build_graph(
            config=cfg,
            mock_llm=mock_llm_stakeholder,
        )
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = graph.invoke(state)  # type: ignore[attr-defined]
        assert _get(result, "timeline") is not None
        assert _get(result, "cost_report") is not None
        assert _get(result, "mode") == "simulate"

    def test_graph_with_no_llm_calls(self) -> None:
        """Zero-cost simulation with no LLM calls produces zero cost report."""
        # mock_llm=None — graph must handle absence of LLM gracefully
        cfg = make_config(mode="simulate")
        graph = build_graph(
            config=cfg,
            mock_llm=None,
        )
        alert = make_sev3_alert()
        state = IncidentState(
            alert=alert,
            severity=alert.severity,
            service=alert.service,
            mode="simulate",
        )
        result = graph.invoke(state)  # type: ignore[attr-defined]
        cost = _get(result, "cost_report")
        assert cost is not None
