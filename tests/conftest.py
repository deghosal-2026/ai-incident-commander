"""Shared fixtures and mock LLM for integration tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from incident_commander.config import Config
from incident_commander.models.input import Runbook
from incident_commander.models.state import (
    Alert,
    ChatMessage,
    GitHubPR,
    IncidentState,
    LogEntry,
)

# Fixed reference time so all test timestamps are deterministic
NOW = datetime(2026, 7, 13, 12, 0, 0)


def mock_llm_stakeholder(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
    """Mock LLM that returns a valid stakeholder update response."""
    # Only responds to "comms" task; other tasks return empty — tests must use the correct task
    if task == "comms":
        return (
            "IMPACT: Payment failures affecting 5% of users\n"
            "ROOT_CAUSE: Database connection pool exhaustion\n"
            "ACTION: Rolling back recent deploy to v2.1.0\n"
            "CONFIDENCE: 0.85\n",
            {"model": "mock", "input_tokens": 50, "output_tokens": 30, "cost": 0.0},
        )
    return ("", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})


def mock_llm_remediation(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
    """Mock LLM that returns a valid remediation suggestion."""
    # Dual-purpose: supports "analysis" (remediation) and "comms" (stakeholder update)
    if task == "analysis":
        return (
            "ACTION: Rollback deploy to v2.1.0\n"
            "CITATION: runbook/db-rollback.md\n"
            "CONFIDENCE: 0.85\n"
            "SIMILAR_INCIDENTS: INC-2023-042, INC-2024-015\n",
            {"model": "mock", "input_tokens": 60, "output_tokens": 40, "cost": 0.0},
        )
    if task == "comms":
        return (
            "IMPACT: Payment failures affecting 5% of users\n"
            "ROOT_CAUSE: Database connection pool exhaustion\n"
            "ACTION: Rolling back recent deploy to v2.1.0\n"
            "CONFIDENCE: 0.85\n",
            {"model": "mock", "input_tokens": 50, "output_tokens": 30, "cost": 0.0},
        )
    return ("", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})


def mock_llm_postmortem_full(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
    """Mock LLM that returns a full 8-section postmortem (SEV1)."""
    # Returns all 8 sections (SEV1-only sections like CUSTOMER_IMPACT included)
    if task == "postmortem":
        return (
            "SUMMARY: Database connection pool exhaustion caused a 12-minute outage\n"
            "CUSTOMER_IMPACT: 5% of users experienced payment failures\n"
            "TIMELINE: Incident timeline from session data\n"
            "ROOT_CAUSE_ANALYSIS: Connection pool exhausted by connection leak\n"
            "SYSTEMIC_CONTRIBUTING_FACTORS: No circuit breaker for DB connections\n"
            "ACTION_ITEMS:\n"
            "- Add circuit breaker | Database team, P0\n"
            "- Increase connection pool limit | SRE, P1\n"
            "STAKEHOLDER_COMMUNICATION_LOG: Updates sent at 12:05, 12:10, 12:15\n"
            "REGULATORY_COMPLIANCE_IMPACT: No regulatory impact identified\n",
            {"model": "mock", "input_tokens": 100, "output_tokens": 200, "cost": 0.0},
        )
    if task == "comms":
        return (
            "IMPACT: Payment failures\nROOT_CAUSE: DB pool\nACTION: Rollback\nCONFIDENCE: 0.9\n",
            {"model": "mock", "input_tokens": 50, "output_tokens": 30, "cost": 0.0},
        )
    return ("", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})


def mock_llm_postmortem_minimal(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
    """Mock LLM that returns minimal postmortem (SEV3, no customer impact)."""
    if task == "postmortem":
        return (
            "SUMMARY: Minor latency spike resolved by auto-scaling\n"
            "TIMELINE: From session data\n"
            "ROOT_CAUSE_ANALYSIS: Traffic surge\n"
            "SYSTEMIC_CONTRIBUTING_FACTORS: Auto-scaling trigger too slow\n"
            "ACTION_ITEMS:\n"
            "- Tune auto-scaling threshold | SRE, P1\n",
            {"model": "mock", "input_tokens": 80, "output_tokens": 100, "cost": 0.0},
        )
    if task == "comms":
        return (
            "IMPACT: Latency spike\nROOT_CAUSE: Traffic\nACTION: Auto-scaled\nCONFIDENCE: 0.9\n",
            {"model": "mock", "input_tokens": 50, "output_tokens": 30, "cost": 0.0},
        )
    return ("", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})


def mock_llm_missing_citation(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
    """Mock LLM that returns a remediation without citation (should be rejected)."""
    if task == "analysis":
        return (
            "ACTION: Restart the database\n"
            "CONFIDENCE: 0.6\n"
            "SIMILAR_INCIDENTS: none\n",
            {"model": "mock", "input_tokens": 50, "output_tokens": 30, "cost": 0.0},
        )
    return ("", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})


def mock_llm_malformed(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
    """Mock LLM that returns malformed/unstructured text."""
    return (
        "This is unstructured text that doesn't follow the required format.",
        {"model": "mock", "input_tokens": 10, "output_tokens": 20, "cost": 0.0},
    )


def mock_llm_empty_timeline(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
    """Mock LLM for state with no timeline events."""
    if task == "comms":
        return (
            "IMPACT: No events\nROOT_CAUSE: Unknown\nACTION: Monitoring\nCONFIDENCE: 0.5\n",
            {"model": "mock", "input_tokens": 10, "output_tokens": 15, "cost": 0.0},
        )
    return ("", {"model": "mock", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})


def make_sev1_alert() -> Alert:
    """Create a SEV1 alert fixture."""
    return Alert(
        severity="SEV1",
        service="payment-service",
        summary="Database connection pool exhaustion — payment failures",
        source="datadog",
        timestamp=NOW,
        incident_id="test-sev1-001",
    )


def make_sev3_alert() -> Alert:
    """Create a SEV3 alert fixture."""
    return Alert(
        severity="SEV3",
        service="web-service",
        summary="Latency spike on /api/checkout",
        source="grafana",
        timestamp=NOW,
        incident_id="test-sev3-001",
    )


def make_sample_logs() -> list[LogEntry]:
    """Create sample log entries."""
    return [
        LogEntry(
            timestamp=NOW - timedelta(minutes=10),
            level="ERROR",
            message="Connection pool exhausted",
            source="payment-service",
        ),
        LogEntry(
            timestamp=NOW - timedelta(minutes=5),
            level="WARN",
            message="High latency detected",
            source="payment-service",
        ),
    ]


def make_sample_messages() -> list[ChatMessage]:
    """Create sample chat messages."""
    return [
        ChatMessage(
            timestamp=NOW - timedelta(minutes=8),
            author="alice",
            text="Seeing payment failures in prod",
            channel="#incidents",
        ),
    ]


def make_sample_prs() -> list[GitHubPR]:
    """Create sample GitHub PRs."""
    return [
        GitHubPR(
            number=101,
            title="fix: update DB connection pool settings",
            author="bob",
            merge_time=NOW - timedelta(minutes=15),
        ),
    ]


def make_sample_runbooks() -> list[Runbook]:
    """Create sample runbooks."""
    return [
        Runbook(
            id="rb-001",
            title="Database Connection Pool Tuning",
            content="Steps to diagnose and fix connection pool issues...",
            keywords=["database", "connection", "pool"],
            service="payment-service",
        ),
    ]


def make_state_with_alert(
    alert: Alert,
    logs: list[LogEntry] | None = None,
    messages: list[ChatMessage] | None = None,
    prs: list[GitHubPR] | None = None,
    **overrides: object,
) -> IncidentState:
    """Build an IncidentState populated with test data."""
    defaults: dict[str, Any] = {
        "severity": alert.severity,
        "service": alert.service,
        "incident_id": alert.incident_id or "test-incident",
        "alert": alert,
        "input_logs": logs or [],
        "input_messages": messages or [],
        "input_prs": prs or [],
        "mode": "simulate",
    }
    defaults.update(overrides)
    return IncidentState(**defaults)


def make_config(**overrides: object) -> Config:
    """Create a Config with test defaults."""
    defaults: dict[str, Any] = {
        "mode": "simulate",
        "confidence_threshold": 0.7,
        "deploy_correlation_window_minutes": 30,
        "session_dir": "/tmp/test-sessions",
    }
    defaults.update(overrides)
    return Config(**defaults)
