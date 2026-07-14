"""Tests for all Pydantic models: validation, defaults, enums, edge cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from incident_commander.models import (
    ActionItem,
    Alert,
    ChatMessage,
    CostReport,
    DeployCorrelation,
    GitHubPR,
    IncidentInput,
    IncidentMeta,
    IncidentResult,
    IncidentState,
    LLMCall,
    LogEntry,
    NodeCost,
    Postmortem,
    PostmortemSection,
    RemediationSuggestion,
    Runbook,
    SessionMeta,
    StakeholderUpdate,
    TimelineEvent,
)

# Fixed timestamp for deterministic tests — avoids time-based flakiness
NOW = datetime(2026, 7, 12, 12, 0, 0)


def valid_alert(**overrides: object) -> dict[str, Any]:
    """Build a valid Alert dict with optional overrides."""
    # Base alert: SEV1 on payment-service triggered manually at NOW
    base = {
        "severity": "SEV1",
        "service": "payment-service",
        "summary": "Error rate exceeds threshold",
        "source": "manual",
        "timestamp": NOW,
    }
    base.update(overrides)
    return base


def valid_timeline_event(**overrides: object) -> dict[str, Any]:
    """Build a valid TimelineEvent dict with optional overrides."""
    # Base event: alert-sourced, high trust, fired at NOW
    base = {
        "timestamp": NOW,
        "source": "alert",
        "event_type": "alert_fired",
        "content": "test",
        "trust_level": "high",
    }
    base.update(overrides)
    return base


def valid_deploy_correlation(**overrides: object) -> dict[str, Any]:
    """Build a valid DeployCorrelation dict with optional overrides."""
    # Base correlation: PR #100 merged 10 min before the alert
    base = {
        "pr_number": 100,
        "pr_title": "fix: resolve pool leak",
        "author": "dev",
        "merge_time": NOW,
        "minutes_before_alert": 10,
    }
    base.update(overrides)
    return base


def valid_stakeholder_update(**overrides: object) -> dict[str, Any]:
    """Build a valid StakeholderUpdate dict with optional overrides."""
    # Base update: first update, rollback action, both times at NOW
    base = {
        "update_number": 1,
        "impact": "2% failures",
        "root_cause_hypothesis": "pool exhausted",
        "action": "rollback",
        "next_update_time": NOW,
        "timestamp": NOW,
    }
    base.update(overrides)
    return base


def valid_remediation(**overrides: object) -> dict[str, Any]:
    """Build a valid RemediationSuggestion dict with optional overrides."""
    # Base remediation: rollback action citing a runbook, 0.85 confidence
    base = {
        "action": "Rollback PR #100",
        "citation": "runbooks/payment-service.md",
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


def valid_postmortem_section(**overrides: object) -> dict[str, Any]:
    """Build a valid PostmortemSection dict with optional overrides."""
    # Base section: a Summary section flagged as AI-generated
    base = {
        "title": "Summary",
        "content": "The incident affected...",
        "ai_generated": True,
    }
    base.update(overrides)
    return base


def valid_action_item(**overrides: object) -> dict[str, Any]:
    """Build a valid ActionItem dict with optional overrides."""
    # Base item: P1 action owned by platform-team
    base = {
        "description": "Add connection pooling",
        "suggested_owner": "platform-team",
        "priority": "P1",
    }
    base.update(overrides)
    return base


def valid_postmortem(**overrides: object) -> dict[str, Any]:
    """Build a valid Postmortem dict with optional overrides."""
    # Base postmortem: SEV1 with all required sections + one action item
    base = {
        "incident_id": "INC-001",
        "incident_date": NOW,
        "severity": "SEV1",
        "service": "payment-service",
        "summary": valid_postmortem_section(),
        "timeline": valid_postmortem_section(title="Timeline"),
        "root_cause_analysis": valid_postmortem_section(title="Root Cause Analysis"),
        "systemic_contributing_factors": valid_postmortem_section(title="Systemic Factors"),
        "action_items": [valid_action_item()],
    }
    base.update(overrides)
    return base


def valid_node_cost(**overrides: object) -> dict[str, Any]:
    """Build a valid NodeCost dict with optional overrides."""
    # Base node: build_timeline node using local model, 150 tokens, $0 cost
    base = {
        "node_name": "build_timeline",
        "llm_model": "ollama/qwen2.5-coder:7b",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "estimated_cost_usd": 0.0,
        "latency_ms": 200,
    }
    base.update(overrides)
    return base


def valid_cost_report(**overrides: object) -> dict[str, Any]:
    """Build a valid CostReport dict with optional overrides."""
    # Base report: 1500 total tokens, $0.05 cost, one node, local model only
    base = {
        "session_id": "sess-001",
        "total_input_tokens": 1000,
        "total_output_tokens": 500,
        "total_tokens": 1500,
        "total_estimated_cost_usd": 0.05,
        "per_node": [valid_node_cost()],
        "models_used": ["ollama/qwen2.5-coder:7b"],
    }
    base.update(overrides)
    return base


def valid_chat_message(**overrides: object) -> dict[str, Any]:
    """Build a valid ChatMessage dict with optional overrides."""
    # Base message: alice in #incidents channel at NOW
    base = {
        "timestamp": NOW,
        "author": "alice",
        "text": "Checking logs now",
        "channel": "#incidents",
    }
    base.update(overrides)
    return base


def valid_log_entry(**overrides: object) -> dict[str, Any]:
    """Build a valid LogEntry dict with optional overrides."""
    # Base log: ERROR-level message from payment-service at NOW
    base = {
        "timestamp": NOW,
        "level": "ERROR",
        "message": "Connection timeout",
        "source": "payment-service",
    }
    base.update(overrides)
    return base


def valid_github_pr(**overrides: object) -> dict[str, Any]:
    """Build a valid GitHubPR dict with optional overrides."""
    # Base PR: #100 fixing pool leak, merged by dev at NOW
    base = {
        "number": 100,
        "title": "fix: resolve pool leak",
        "author": "dev",
        "merge_time": NOW,
    }
    base.update(overrides)
    return base


def valid_runbook(**overrides: object) -> dict[str, Any]:
    """Build a valid Runbook dict with optional overrides."""
    # Base runbook: DB Pool Exhaustion guide for payment-service
    base = {
        "id": "rb-001",
        "title": "DB Pool Exhaustion",
        "content": "## Triage\nCheck connections",
        "keywords": ["db", "pool"],
        "service": "payment-service",
    }
    base.update(overrides)
    return base


def valid_incident_meta(**overrides: object) -> dict[str, Any]:
    """Build a valid IncidentMeta dict with optional overrides."""
    # Base meta: INC-001, SEV1 on payment-service starting at NOW
    base = {
        "incident_id": "INC-001",
        "service": "payment-service",
        "severity": "SEV1",
        "start_time": NOW,
    }
    base.update(overrides)
    return base


class TestAlert:
    """Tests for the Alert model."""

    def test_valid(self) -> None:
        """A valid alert dict produces a correct Alert instance."""
        alert = Alert(**valid_alert())
        # Severity enum is preserved as string
        assert alert.severity == "SEV1"
        # Service name is preserved as-is
        assert alert.service == "payment-service"

    def test_invalid_severity(self) -> None:
        """An out-of-range severity raises ValidationError."""
        # SEV4 is outside the valid SEV1–SEV3 range
        with pytest.raises(ValidationError):
            Alert(**valid_alert(severity="SEV4"))

    def test_missing_required(self) -> None:
        """Missing all required fields raises ValidationError."""
        # Empty dict means all required fields are absent
        with pytest.raises(ValidationError):
            Alert(**{})

    def test_default_source(self) -> None:
        """The source field defaults to 'manual'."""
        alert = Alert(severity="SEV2", service="api-gateway", summary="test", timestamp=NOW)
        # source omitted from constructor — should default to "manual"
        assert alert.source == "manual"


class TestTimelineEvent:
    """Tests for the TimelineEvent model."""

    def test_valid(self) -> None:
        """A valid timeline event dict produces a correct TimelineEvent."""
        event = TimelineEvent(**valid_timeline_event())
        # source enum: "alert" is one of the valid source types
        assert event.source == "alert"
        # trust_level enum: "high" is the highest trust tier
        assert event.trust_level == "high"

    def test_invalid_source(self) -> None:
        """An invalid source raises ValidationError."""
        # "pagerduty" is not a valid source enum value
        with pytest.raises(ValidationError):
            TimelineEvent(**valid_timeline_event(source="pagerduty"))

    def test_invalid_trust_level(self) -> None:
        """An invalid trust level raises ValidationError."""
        # "very_high" is not a valid trust_level enum (only high/medium/low)
        with pytest.raises(ValidationError):
            TimelineEvent(**valid_timeline_event(trust_level="very_high"))

    def test_missing_required(self) -> None:
        """Missing all required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            TimelineEvent(**{})

    def test_deploy_correlation_default(self) -> None:
        """The deploy_correlation flag defaults to False."""
        event = TimelineEvent(**valid_timeline_event())
        # deploy_correlation is optional and defaults to False
        assert event.deploy_correlation is False


class TestDeployCorrelation:
    """Tests for the DeployCorrelation model."""

    def test_valid(self) -> None:
        """A valid deploy correlation dict produces a correct instance."""
        dc = DeployCorrelation(**valid_deploy_correlation())
        assert dc.pr_number == 100
        # Default strength is "strong" for 10 min before alert
        assert dc.correlation_strength == "strong"

    def test_invalid_strength(self) -> None:
        """An invalid correlation strength raises ValidationError."""
        # "super_strong" is not a valid correlation_strength enum
        with pytest.raises(ValidationError):
            DeployCorrelation(**valid_deploy_correlation(correlation_strength="super_strong"))

    def test_default_strength(self) -> None:
        """The correlation_strength defaults to 'strong'."""
        dc = DeployCorrelation(**valid_deploy_correlation())
        # correlation_strength not set in base dict — defaults to "strong"
        assert dc.correlation_strength == "strong"


class TestStakeholderUpdate:
    """Tests for the StakeholderUpdate model."""

    def test_valid(self) -> None:
        """A valid stakeholder update dict produces a correct instance."""
        su = StakeholderUpdate(**valid_stakeholder_update())
        assert su.update_number == 1
        # confidence not set in base dict — defaults to 1.0 (fully certain)
        assert su.confidence == 1.0

    def test_default_confidence(self) -> None:
        """The confidence field defaults to 1.0."""
        su = StakeholderUpdate(**valid_stakeholder_update())
        assert su.confidence == 1.0

    def test_default_approved(self) -> None:
        """The approved flag defaults to False."""
        su = StakeholderUpdate(**valid_stakeholder_update())
        # approved defaults to False — updates need human sign-off
        assert su.approved is False


class TestRemediationSuggestion:
    """Tests for the RemediationSuggestion model."""

    def test_valid(self) -> None:
        """A valid remediation dict produces a correct instance."""
        rs = RemediationSuggestion(**valid_remediation())
        assert rs.action == "Rollback PR #100"
        # Confidence 0.85 is above the default threshold (0.7)
        assert rs.confidence == 0.85

    def test_default_dry_run(self) -> None:
        """The dry_run_outcome field defaults to empty string."""
        rs = RemediationSuggestion(**valid_remediation())
        # dry_run_outcome not set in base — defaults to empty string
        assert rs.dry_run_outcome == ""

    def test_default_approved(self) -> None:
        """The approved flag defaults to False."""
        rs = RemediationSuggestion(**valid_remediation())
        # approved defaults to False — remediations need human sign-off
        assert rs.approved is False


class TestPostmortemSection:
    """Tests for the PostmortemSection model."""

    def test_valid(self) -> None:
        """A valid postmortem section dict produces a correct instance."""
        ps = PostmortemSection(**valid_postmortem_section())
        assert ps.title == "Summary"
        # ai_generated=True in base dict — sections are AI-drafted by default
        assert ps.ai_generated is True

    def test_ai_generated_default(self) -> None:
        """The ai_generated flag defaults to True."""
        ps = PostmortemSection(**valid_postmortem_section())
        # ai_generated defaults to True when not explicitly set
        assert ps.ai_generated is True


class TestActionItem:
    """Tests for the ActionItem model."""

    def test_valid(self) -> None:
        """A valid action item dict produces a correct instance."""
        ai = ActionItem(**valid_action_item())
        assert ai.description == "Add connection pooling"
        assert ai.suggested_owner == "platform-team"

    def test_invalid_priority(self) -> None:
        """An invalid priority raises ValidationError."""
        # P3 is not a valid priority enum (only P1 and P2)
        with pytest.raises(ValidationError):
            ActionItem(**valid_action_item(priority="P3"))

    def test_default_priority(self) -> None:
        """The priority field defaults to 'P1'."""
        ai = ActionItem(**valid_action_item())
        # priority not overridden — defaults to P1 (highest urgency)
        assert ai.priority == "P1"

    def test_ai_generated_default(self) -> None:
        """The ai_generated flag defaults to True."""
        ai = ActionItem(**valid_action_item())
        # ai_generated defaults to True — action items are AI-suggested
        assert ai.ai_generated is True


class TestPostmortem:
    """Tests for the Postmortem model."""

    def test_valid_sev1(self) -> None:
        """A valid SEV1 postmortem produces a correct instance."""
        pm = Postmortem(**valid_postmortem())
        assert pm.severity == "SEV1"
        # Base dict provides exactly one action item
        assert len(pm.action_items) == 1

    def test_sev1_optional_sections(self) -> None:
        """SEV1 postmortems accept optional sections."""
        pm = Postmortem(
            **valid_postmortem(
                customer_impact=valid_postmortem_section(title="Customer Impact"),
                stakeholder_communication_log=valid_postmortem_section(title="Comm Log"),
                regulatory_compliance_impact=valid_postmortem_section(title="Regulatory"),
            )
        )
        # SEV1 requires all optional sections — verify they're stored
        assert pm.customer_impact is not None
        assert pm.stakeholder_communication_log is not None
        assert pm.regulatory_compliance_impact is not None

    def test_sev3_no_optional_sections(self) -> None:
        """SEV3 postmortems leave optional sections as None."""
        pm = Postmortem(**valid_postmortem(severity="SEV3"))
        # SEV3 doesn't require optional sections — they stay None
        assert pm.customer_impact is None
        assert pm.stakeholder_communication_log is None
        assert pm.regulatory_compliance_impact is None

    def test_missing_required_section(self) -> None:
        """A missing required section raises ValidationError."""
        # summary is a required section — setting it to None must fail
        with pytest.raises(ValidationError):
            Postmortem(**valid_postmortem(summary=None))

    def test_empty_action_items(self) -> None:
        """An empty action_items list is accepted."""
        pm = Postmortem(**valid_postmortem(action_items=[]))
        # Empty list is valid — no action items for this incident
        assert pm.action_items == []

    def test_default_approved(self) -> None:
        """The approved flag defaults to False."""
        pm = Postmortem(**valid_postmortem())
        # approved defaults to False — postmortems need human review
        assert pm.approved is False


class TestNodeCost:
    """Tests for the NodeCost model."""

    def test_valid(self) -> None:
        """A valid node cost dict produces a correct instance."""
        nc = NodeCost(**valid_node_cost())
        assert nc.node_name == "build_timeline"
        # total_tokens = input + output = 100 + 50 = 150
        assert nc.total_tokens == 150

    def test_zero_tokens_valid(self) -> None:
        """Zero token counts are accepted."""
        nc = NodeCost(**valid_node_cost(input_tokens=0, output_tokens=0, total_tokens=0))
        # Zero tokens is valid — e.g., a cached or no-op node
        assert nc.total_tokens == 0


class TestCostReport:
    """Tests for the CostReport model."""

    def test_valid(self) -> None:
        """A valid cost report dict produces a correct instance."""
        cr = CostReport(**valid_cost_report())
        assert cr.session_id == "sess-001"
        # Base dict provides exactly one per-node breakdown
        assert len(cr.per_node) == 1

    def test_empty_models(self) -> None:
        """An empty models_used list is accepted."""
        cr = CostReport(**valid_cost_report(models_used=[]))
        # Empty models list is valid — no LLM calls were made
        assert cr.models_used == []


class TestAlertEdgeCases:
    """Edge-case tests for the Alert model."""

    def test_empty_metadata(self) -> None:
        """The metadata field defaults to an empty dict."""
        alert = Alert(**valid_alert())
        # metadata not set in base dict — defaults to empty dict
        assert alert.metadata == {}

    def test_custom_metadata(self) -> None:
        """Custom metadata is preserved on the Alert instance."""
        alert = Alert(**valid_alert(metadata={"region": "us-east-1", "team": "infra"}))
        # Custom metadata dict is preserved verbatim
        assert alert.metadata["region"] == "us-east-1"


class TestTimelineEventEdgeCases:
    """Edge-case tests for the TimelineEvent model."""

    def test_all_sources_valid(self) -> None:
        """All defined source values are accepted."""
        # Iterate all valid source enum values to confirm acceptance
        for src in ["alert", "chat", "log", "github", "manual"]:
            event = TimelineEvent(**valid_timeline_event(source=src))
            assert event.source == src

    def test_all_trust_levels_valid(self) -> None:
        """All defined trust level values are accepted."""
        # Iterate all valid trust_level enum values to confirm acceptance
        for tl in ["high", "medium", "low"]:
            event = TimelineEvent(**valid_timeline_event(trust_level=tl))
            assert event.trust_level == tl


class TestInputModels:
    """Tests for the input-related models."""

    def test_chat_message_valid(self) -> None:
        """A valid chat message dict produces a correct instance."""
        cm = ChatMessage(**valid_chat_message())
        # Author field is preserved from base dict
        assert cm.author == "alice"

    def test_log_entry_valid(self) -> None:
        """A valid log entry dict produces a correct instance."""
        le = LogEntry(**valid_log_entry())
        # ERROR is a valid log level enum value
        assert le.level == "ERROR"

    def test_log_entry_invalid_level(self) -> None:
        """An invalid log level raises ValidationError."""
        # CRITICAL is not a valid log level (only ERROR, WARN, INFO, DEBUG)
        with pytest.raises(ValidationError):
            LogEntry(**valid_log_entry(level="CRITICAL"))

    def test_github_pr_valid(self) -> None:
        """A valid GitHubPR dict produces a correct instance."""
        pr = GitHubPR(**valid_github_pr())
        # PR number is preserved from base dict
        assert pr.number == 100

    def test_runbook_valid(self) -> None:
        """A valid Runbook dict produces a correct instance."""
        rb = Runbook(**valid_runbook())
        # Runbook ID is preserved from base dict
        assert rb.id == "rb-001"

    def test_incident_meta_valid(self) -> None:
        """A valid IncidentMeta dict produces a correct instance."""
        im = IncidentMeta(**valid_incident_meta())
        # Severity is preserved from base dict
        assert im.severity == "SEV1"

    def test_incident_input_valid(self) -> None:
        """A minimal IncidentInput uses the default schema version."""
        # Only alert is provided — all other input collections default to empty
        inp = IncidentInput(alert=Alert(**valid_alert()))
        # schema_version defaults to "0.1.0" when not specified
        assert inp.schema_version == "0.1.0"
        # logs list defaults to empty when not provided
        assert len(inp.logs) == 0

    def test_incident_input_optional_fields(self) -> None:
        """IncidentInput accepts all optional input collections."""
        # Provide all optional input collections at once
        inp = IncidentInput(
            alert=Alert(**valid_alert()),
            logs=[LogEntry(**valid_log_entry())],
            messages=[ChatMessage(**valid_chat_message())],
            github=[GitHubPR(**valid_github_pr())],
            runbooks=[Runbook(**valid_runbook())],
        )
        # Each optional collection has exactly one item
        assert len(inp.logs) == 1
        assert len(inp.messages) == 1

    def test_incident_input_missing_alert(self) -> None:
        """A missing alert raises ValidationError."""
        # alert is the only required field — omitting it must fail
        with pytest.raises(ValidationError):
            IncidentInput(**{})


class TestOutputModels:
    """Tests for the output-related models."""

    def test_incident_result_defaults(self) -> None:
        """IncidentResult defaults to empty collections."""
        result = IncidentResult(thread_id="test-001")
        assert result.thread_id == "test-001"
        # timeline defaults to empty list when not provided
        assert result.timeline == []
        # deploy_correlations defaults to empty list
        assert result.deploy_correlations == []

    def test_session_meta_defaults(self) -> None:
        """SessionMeta defaults to simulate mode and not auto-approved."""
        meta = SessionMeta(thread_id="test-001")
        # mode defaults to "simulate" — safe default, no real actions
        assert meta.mode == "simulate"
        # auto_approved defaults to False — needs human approval
        assert meta.auto_approved is False

    def test_to_markdown_returns_dict(self) -> None:
        """to_markdown returns a dict with expected section keys."""
        result = IncidentResult(thread_id="test-001")
        md = result.to_markdown()
        # Each key maps to a markdown section filename
        assert "incident-summary.md" in md
        assert "timeline.md" in md
        assert "stakeholder-updates.md" in md
        assert "comms-blocks.md" in md
        assert "remediation.md" in md
        assert "postmortem.md" in md
        assert "cost-report.md" in md

    def test_to_json_returns_dict(self) -> None:
        """to_json returns a dict containing the thread_id."""
        result = IncidentResult(thread_id="test-001")
        js = result.to_json()
        # thread_id is included in the JSON output dict
        assert js["thread_id"] == "test-001"


class TestIncidentState:
    """Tests for the IncidentState model."""

    def test_defaults(self) -> None:
        """IncidentState defaults to SEV3 and empty collections."""
        state = IncidentState()
        # Default severity is SEV3 (lowest) until an alert sets it
        assert state.severity == "SEV3"
        # All timeline/correlation collections start empty
        assert state.timeline == []
        assert state.deploy_correlations == []
        # All input collections start empty — data is added as it arrives
        assert state.input_logs == []
        assert state.input_messages == []
        assert state.input_prs == []
        assert state.input_manual_events == []
        # Retrieved runbooks start empty
        assert state.retrieved_runbooks == []
        # Output collections start empty — populated by graph nodes
        assert state.stakeholder_updates == []
        assert state.remediation_suggestions == []
        # postmortem not yet generated
        assert state.postmortem is None
        # cost_report not yet generated
        assert state.cost_report is None
        # Incident is not resolved by default
        assert state.resolved is False

    def test_with_alert(self) -> None:
        """IncidentState accepts an alert."""
        state = IncidentState(alert=Alert(**valid_alert()))
        # Alert is stored on the state object
        assert state.alert is not None
        # Alert severity flows through from the valid_alert base dict
        assert state.alert.severity == "SEV1"

    def test_with_input_data(self) -> None:
        """IncidentState accepts input logs, messages, and PRs."""
        state = IncidentState(
            input_logs=[LogEntry(**valid_log_entry())],
            input_messages=[ChatMessage(**valid_chat_message())],
            input_prs=[GitHubPR(**valid_github_pr())],
        )
        # Each input collection has exactly one item
        assert len(state.input_logs) == 1
        assert len(state.input_messages) == 1
        assert len(state.input_prs) == 1

    def test_with_timeline(self) -> None:
        """IncidentState accepts a timeline of events."""
        state = IncidentState(timeline=[TimelineEvent(**valid_timeline_event())])
        # Timeline with one event is stored on state
        assert len(state.timeline) == 1

    def test_with_postmortem(self) -> None:
        """IncidentState accepts a postmortem."""
        pm = Postmortem(**valid_postmortem())
        state = IncidentState(postmortem=pm)
        # Postmortem object is stored on state
        assert state.postmortem is not None
        # incident_id flows through from the valid_postmortem base dict
        assert state.postmortem.incident_id == "INC-001"

    def test_resolved_flag(self) -> None:
        """The resolved flag can be set to True."""
        state = IncidentState(resolved=True)
        # resolved can be set to True to mark incident closure
        assert state.resolved is True


class TestModelDefaults:
    """Default values and edge cases across models."""

    def test_log_entry_trace_level(self) -> None:
        """LogEntry accepts TRACE as a valid level."""
        le = LogEntry(timestamp=NOW, level="TRACE", message="verbose debug")
        assert le.level == "TRACE"

    def test_github_pr_default_base_branch(self) -> None:
        """GitHubPR defaults base_branch to 'main'."""
        pr = GitHubPR(number=1, title="fix", author="dev", merge_time=NOW)
        assert pr.base_branch == "main"

    def test_incident_meta_default_lists(self) -> None:
        """IncidentMeta defaults oncall_roster and tags to empty lists."""
        im = IncidentMeta(
            incident_id="INC-001", service="pay", severity="SEV1", start_time=NOW
        )
        assert im.oncall_roster == []
        assert im.tags == []

    def test_llm_call_default_response_truncated(self) -> None:
        """LLMCall defaults response_truncated to False."""
        call = LLMCall(
            call_id="c1", timestamp=NOW, node_name="n1", model="m1",
            input_tokens=0, output_tokens=0, total_tokens=0, latency_ms=0,
        )
        assert call.response_truncated is False

    def test_session_meta_minimal(self) -> None:
        """SessionMeta with only thread_id uses all defaults."""
        meta = SessionMeta(thread_id="t-1")
        assert meta.models_used == []
        assert meta.total_cost_usd == 0.0
        assert meta.total_tokens == 0
        assert meta.mode == "simulate"
        assert meta.auto_approved is False


class TestIncidentResultToMarkdown:
    """IncidentResult.to_markdown — edge cases."""

    def test_empty_timeline(self) -> None:
        """Empty timeline produces empty string."""
        result = IncidentResult(thread_id="t-1")
        md = result.to_markdown()
        assert md["timeline.md"] == ""

    def test_none_postmortem(self) -> None:
        """None postmortem shows '(none)' in the markdown output."""
        result = IncidentResult(thread_id="t-1")
        md = result.to_markdown()
        assert "(none)" in md["postmortem.md"]

    def test_none_cost_report(self) -> None:
        """None cost_report shows '(none)' in the markdown output."""
        result = IncidentResult(thread_id="t-1")
        md = result.to_markdown()
        assert "(none)" in md["cost-report.md"]

    def test_empty_stakeholder_updates(self) -> None:
        """Empty stakeholder_updates produces empty string."""
        result = IncidentResult(thread_id="t-1")
        md = result.to_markdown()
        assert md["stakeholder-updates.md"] == ""
