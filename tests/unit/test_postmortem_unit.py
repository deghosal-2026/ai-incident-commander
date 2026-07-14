"""Unit tests for postmortem module: _parse_postmortem_response, _build_postmortem_prompt."""

from __future__ import annotations

from datetime import datetime

from incident_commander.models.state import Alert, IncidentState
from incident_commander.nodes.postmortem import _build_postmortem_prompt, _parse_postmortem_response
from tests.conftest import NOW


class TestParsePostmortemResponse:
    """_parse_postmortem_response — parsing LLM postmortem output."""

    def _make_state(self, severity: str = "SEV1", **kwargs: object) -> IncidentState:
        alert = Alert(
            severity=severity,
            service="payment-service",
            summary="DB pool exhausted",
            source="datadog",
            timestamp=NOW,
            incident_id="INC-001",
        )
        return IncidentState(
            alert=alert,
            severity=severity,
            service="payment-service",
            incident_id="INC-001",
            **kwargs,
        )

    def test_prose_line_does_not_trigger_new_section(self) -> None:
        """'The timeline shows...' should NOT trigger a new TIMELINE section."""
        text = (
            "SUMMARY: DB outage\n"
            "The timeline shows connection pool was exhausted at 12:00.\n"
        )
        state = self._make_state()
        pm = _parse_postmortem_response(text, state)
        # "TIMELINE" section should NOT exist because "The timeline shows" is prose
        assert pm.timeline.content == "Timeline — insufficient data."

    def test_timeline_on_own_line_triggers_section(self) -> None:
        """"TIMELINE" on its own line triggers a new section."""
        text = (
            "SUMMARY: DB outage\n"
            "TIMELINE\n"
            "12:00 Alert triggered\n"
            "12:05 Rollback initiated\n"
        )
        state = self._make_state()
        pm = _parse_postmortem_response(text, state)
        assert "12:00 Alert triggered" in pm.timeline.content

    def test_root_cause_analysis_section(self) -> None:
        """"ROOT_CAUSE_ANALYSIS:" triggers section."""
        text = (
            "SUMMARY: DB outage\n"
            "TIMELINE: Events\n"
            "ROOT_CAUSE_ANALYSIS:\n"
            "Connection pool exhausted by connection leak\n"
        )
        state = self._make_state()
        pm = _parse_postmortem_response(text, state)
        assert "Connection pool exhausted" in pm.root_cause_analysis.content

    def test_action_item_with_owner_and_priority(self) -> None:
        """'Fix the bug | Alice, P1' -> owner=Alice, priority=P1."""
        text = (
            "SUMMARY: DB outage\n"
            "ACTION_ITEMS\n"
            "- Fix the bug | Alice, P1\n"
        )
        state = self._make_state()
        pm = _parse_postmortem_response(text, state)
        assert len(pm.action_items) == 1
        item = pm.action_items[0]
        assert item.description == "Fix the bug"
        assert item.suggested_owner == "Alice"
        assert item.priority == "P1"

    def test_action_item_p0_priority(self) -> None:
        """'Fix the bug | Bob, P0' -> priority=P0, owner=Bob."""
        text = (
            "SUMMARY: DB outage\n"
            "ACTION_ITEMS\n"
            "- Fix the bug | Bob, P0\n"
        )
        state = self._make_state()
        pm = _parse_postmortem_response(text, state)
        assert len(pm.action_items) == 1
        item = pm.action_items[0]
        assert item.description == "Fix the bug"
        assert item.suggested_owner == "Bob"
        assert item.priority == "P0"

    def test_action_item_no_pipe_no_comma(self) -> None:
        """'Fix the thing' (no pipe, no comma) -> default item with P2."""
        text = (
            "SUMMARY: DB outage\n"
            "ACTION_ITEMS\n"
            "- Fix the thing\n"
        )
        state = self._make_state()
        pm = _parse_postmortem_response(text, state)
        assert len(pm.action_items) == 1
        item = pm.action_items[0]
        assert item.description == "No specific action items identified."
        assert item.suggested_owner == "TBD"
        assert item.priority == "P2"

    def test_action_items_header_with_no_dash_lines(self) -> None:
        """ACTION_ITEMS header with no '- ' lines -> default item with P2."""
        text = (
            "SUMMARY: DB outage\n"
            "ACTION_ITEMS\n"
            "Some text without dashes\n"
        )
        state = self._make_state()
        pm = _parse_postmortem_response(text, state)
        assert len(pm.action_items) == 1
        assert pm.action_items[0].description == "No specific action items identified."
        assert pm.action_items[0].priority == "P2"

    def test_mttr_computed_with_known_alert_and_resolved_at(self) -> None:
        """Known alert + resolved_at -> MTTR computed correctly (15 min)."""
        alert_time = NOW
        resolved_time = datetime(2026, 7, 13, 12, 15, 0)
        from incident_commander.models.state import TimelineEvent
        state = IncidentState(
            alert=Alert(
                severity="SEV1", service="srv", summary="test",
                source="test", timestamp=alert_time, incident_id="INC-001",
            ),
            severity="SEV1",
            service="srv",
            incident_id="INC-001",
            timeline=[
                TimelineEvent(
                    timestamp=resolved_time,
                    source="manual",
                    event_type="resolved",
                    content="Incident resolved",
                    trust_level="high",
                ),
            ],
        )
        text = "SUMMARY: Test\n"
        pm = _parse_postmortem_response(text, state)
        assert pm.mttr_minutes == 15, f"Expected 15, got {pm.mttr_minutes}"

    def test_sev1_includes_all_sections(self) -> None:
        """SEV1 postmortem includes all severity-conditional sections."""
        state = self._make_state("SEV1")
        text = (
            "SUMMARY: DB outage\n"
            "CUSTOMER_IMPACT: 5% of users affected\n"
            "TIMELINE: Events\n"
            "ROOT_CAUSE_ANALYSIS: Pool leak\n"
            "SYSTEMIC_CONTRIBUTING_FACTORS: No circuit breaker\n"
            "ACTION_ITEMS\n"
            "- Add breaker | DB team, P0\n"
            "STAKEHOLDER_COMMUNICATION_LOG: Updates at 12:05\n"
            "REGULATORY_COMPLIANCE_IMPACT: None\n"
        )
        pm = _parse_postmortem_response(text, state)
        assert pm.customer_impact is not None
        assert pm.stakeholder_communication_log is not None
        assert pm.regulatory_compliance_impact is not None

    def test_sev3_excludes_sev1_only_sections(self) -> None:
        """SEV3 postmortem excludes Customer_Impact, Stakeholder_Comm_Log, Regulatory."""
        state = self._make_state("SEV3")
        text = (
            "SUMMARY: Latency spike\n"
            "TIMELINE: Events\n"
            "ROOT_CAUSE_ANALYSIS: Traffic surge\n"
            "SYSTEMIC_CONTRIBUTING_FACTORS: Auto-scaling slow\n"
            "ACTION_ITEMS\n"
            "- Tune threshold | SRE, P1\n"
        )
        pm = _parse_postmortem_response(text, state)
        assert pm.customer_impact is None
        assert pm.stakeholder_communication_log is None
        assert pm.regulatory_compliance_impact is None


class TestBuildPostmortemPrompt:
    """_build_postmortem_prompt — LLM prompt for postmortem generation."""

    def _make_state(self, severity: str = "SEV1") -> IncidentState:
        alert = Alert(
            severity=severity,
            service="payment-service",
            summary="DB pool exhausted",
            source="datadog",
            timestamp=NOW,
            incident_id="INC-001",
        )
        return IncidentState(
            alert=alert,
            severity=severity,
            service="payment-service",
            incident_id="INC-001",
        )

    def test_sev1_has_all_eight_sections(self) -> None:
        """SEV1 prompt mentions all 8 sections."""
        state = self._make_state("SEV1")
        prompt = _build_postmortem_prompt(state)
        assert "SUMMARY" in prompt
        assert "CUSTOMER_IMPACT" in prompt
        assert "TIMELINE" in prompt
        assert "ROOT_CAUSE_ANALYSIS" in prompt
        assert "SYSTEMIC_CONTRIBUTING_FACTORS" in prompt
        assert "ACTION_ITEMS" in prompt
        assert "STAKEHOLDER_COMMUNICATION_LOG" in prompt
        assert "REGULATORY_COMPLIANCE_IMPACT" in prompt

    def test_prompt_includes_all_sections_no_matter_severity(self) -> None:
        """Prompt always lists all 8 sections; conditionality is in parsing."""
        for sev in ("SEV1", "SEV2", "SEV3"):
            state = self._make_state(sev)
            prompt = _build_postmortem_prompt(state)
            assert "CUSTOMER_IMPACT" in prompt
            assert "STAKEHOLDER_COMMUNICATION_LOG" in prompt
            assert "REGULATORY_COMPLIANCE_IMPACT" in prompt
            assert "ACTION_ITEMS" in prompt
            assert "ROOT_CAUSE_ANALYSIS" in prompt

    def test_all_severities_include_blameless(self) -> None:
        """Prompt includes BLAMELESS rules regardless of severity."""
        for sev in ("SEV1", "SEV2", "SEV3"):
            state = self._make_state(sev)
            prompt = _build_postmortem_prompt(state)
            assert "BLAMELESS" in prompt, f"BLAMELESS not found in {sev} prompt"
