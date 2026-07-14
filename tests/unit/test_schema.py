"""Tests for schema registry: export_schemas, validate_input, SCHEMA_VERSION."""

from __future__ import annotations

import json  # loads() to parse exported JSON schema files for field checks
import tempfile  # TemporaryDirectory for isolated file I/O during export tests
from pathlib import Path  # Path for constructing nested directory paths in tests

import pytest  # provides raises() for testing ValidationError and KeyError
from pydantic import ValidationError  # raised when input fails schema validation

# SCHEMA_VERSION: version string; SCHEMAS: registry; export_schemas/validate_input
from incident_commander.schema import SCHEMA_VERSION, SCHEMAS, export_schemas, validate_input


class TestSchemaRegistry:
    """SCHEMAS registry: 16 schemas mapped to Pydantic models."""

    def test_has_16_schemas(self) -> None:
        """Registry contains exactly 16 named schemas."""
        # Exactly 16 schemas ensures the registry matches the expected model set
        assert len(SCHEMAS) == 16

    def test_has_expected_schemas(self) -> None:
        """All expected schema names are present."""
        # Full set of 16 schema names covering the entire domain model surface
        expected = {
            "alert", "chat-message", "log-entry", "github-pr", "runbook",
            "incident-meta", "incident-input", "incident-result",
            "timeline-event", "deploy-correlation", "stakeholder-update",
            "remediation-suggestion", "postmortem", "cost-report",
            "session-meta", "llm-call",
        }
        assert set(SCHEMAS.keys()) == expected

    def test_schema_version(self) -> None:
        """SCHEMA_VERSION is '0.1.0'."""
        # Version 0.1.0 signals pre-1.0 stability for the schema contract
        assert SCHEMA_VERSION == "0.1.0"


class TestExportSchemas:
    """export_schemas writes JSON Schema files to disk."""

    def test_exports_16_files(self) -> None:
        """export_schemas creates exactly 16 JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_schemas(tmpdir)
            # One .json file per schema; all must exist on disk
            assert len(paths) == 16
            for p in paths:
                assert p.suffix == ".json"
                assert p.exists()

    def test_exported_files_have_schema_fields(self) -> None:
        """Each exported schema has $id, $schema, and title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_schemas(tmpdir)
            for p in paths:
                data = json.loads(p.read_text())
                # $id, $schema, and title are required JSON Schema fields
                assert "$id" in data, f"{p.name} missing $id"
                assert "$schema" in data, f"{p.name} missing $schema"
                assert "title" in data, f"{p.name} missing title"

    def test_export_creates_directory(self) -> None:
        """export_schemas creates the output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Nested path that doesn't exist yet → export_schemas must create it
            nested = Path(tmpdir) / "nested" / "schemas"
            paths = export_schemas(str(nested))
            assert nested.exists()
            assert len(paths) == 16


class TestValidateInput:
    """validate_input checks dicts against Pydantic schemas."""

    def test_valid_alert(self) -> None:
        """Valid alert dict returns True."""
        # Complete alert with valid severity, service, summary, ISO timestamp
        result = validate_input(
            {
                "severity": "SEV1",
                "service": "payment-service",
                "summary": "Error spike",
                "timestamp": "2026-07-12T12:00:00",
            },
            "alert",
        )
        assert result is True

    def test_valid_chat_message(self) -> None:
        """Valid chat message dict returns True."""
        # Chat message with required timestamp, author, text (channel optional)
        result = validate_input(
            {"timestamp": "2026-07-12T12:00:00", "author": "alice", "text": "Checking logs"},
            "chat-message",
        )
        assert result is True

    def test_missing_required_field_raises(self) -> None:
        """Missing required field raises ValidationError."""
        # Alert with only severity (missing service, summary, timestamp)
        with pytest.raises(ValidationError):
            validate_input({"severity": "SEV1"}, "alert")

    def test_invalid_severity_raises(self) -> None:
        """Invalid severity value raises ValidationError."""
        # SEV4 is not a valid severity enum (only SEV1-SEV3 allowed)
        with pytest.raises(ValidationError):
            validate_input(
                {
                    "severity": "SEV4",
                    "service": "test",
                    "summary": "test",
                    "timestamp": "2026-07-12T12:00:00",
                },
                "alert",
            )

    def test_invalid_field_type_raises(self) -> None:
        """Wrong field type raises ValidationError."""
        # timestamp="not-a-date" fails datetime parsing → ValidationError
        with pytest.raises(ValidationError):
            validate_input(
                {
                    "severity": "SEV1",
                    "service": "test",
                    "summary": "test",
                    "timestamp": "not-a-date",
                },
                "alert",
            )

    def test_unknown_schema_raises(self) -> None:
        """Unknown schema name raises KeyError."""
        # "nonexistent" is not a registered schema name → KeyError expected
        with pytest.raises(KeyError) as exc:
            validate_input({}, "nonexistent")
        # Error message must mention the unknown name and list available schemas
        assert "nonexistent" in str(exc.value)
        assert "alert" in str(exc.value)  # available schemas listed

    def test_valid_log_entry(self) -> None:
        """Valid log entry dict returns True."""
        # Log entry with required timestamp, level, message (source optional)
        result = validate_input(
            {"timestamp": "2026-07-12T12:00:00", "level": "ERROR", "message": "Connection timeout"},
            "log-entry",
        )
        assert result is True

    def test_valid_timeline_event(self) -> None:
        """Valid timeline event dict returns True."""
        # Timeline event with all 5 required fields: timestamp, source, type, content, trust
        result = validate_input(
            {
                "timestamp": "2026-07-12T12:00:00",
                "source": "alert",
                "event_type": "alert_fired",
                "content": "test",
                "trust_level": "high",
            },
            "timeline-event",
        )
        assert result is True

    # ── Parametrized valid/invalid tests across all 16 schemas ──────────

    _VALID_SCHEMAS = [
        ("alert",
         {"severity": "SEV1", "service": "pay", "summary": "err",
          "timestamp": "2026-07-12T12:00:00"}),
        ("chat-message",
         {"timestamp": "2026-07-12T12:00:00", "author": "alice", "text": "hello"}),
        ("log-entry",
         {"timestamp": "2026-07-12T12:00:00", "level": "ERROR", "message": "boom"}),
        ("github-pr",
         {"number": 1, "title": "fix", "author": "bob",
          "merge_time": "2026-07-12T12:00:00"}),
        ("runbook",
         {"title": "DB Pool Exhaustion", "content": "## Triage\nCheck connections"}),
        ("incident-meta",
         {"incident_id": "INC-001", "service": "pay", "severity": "SEV1",
          "start_time": "2026-07-12T12:00:00"}),
        ("incident-input",
         {"alert": {"severity": "SEV1", "service": "pay", "summary": "err",
                     "timestamp": "2026-07-12T12:00:00"}}),
        ("incident-result", {"thread_id": "t-1"}),
        ("timeline-event",
         {"timestamp": "2026-07-12T12:00:00", "source": "alert",
          "event_type": "fired", "content": "test", "trust_level": "high"}),
        ("deploy-correlation",
         {"pr_number": 1, "pr_title": "fix", "author": "bob",
          "merge_time": "2026-07-12T12:00:00", "minutes_before_alert": 10}),
        ("stakeholder-update",
         {"update_number": 1, "impact": "x", "root_cause_hypothesis": "y",
          "action": "z", "next_update_time": "2026-07-12T12:00:00",
          "timestamp": "2026-07-12T12:00:00"}),
        ("remediation-suggestion",
         {"action": "rollback", "citation": "runbook.md", "confidence": 0.8}),
        ("postmortem",
         {"incident_id": "INC-001", "incident_date": "2026-07-12T12:00:00",
          "severity": "SEV1", "service": "pay",
          "summary": {"title": "S", "content": "C"},
          "timeline": {"title": "T", "content": "C"},
          "root_cause_analysis": {"title": "R", "content": "C"},
          "systemic_contributing_factors": {"title": "S", "content": "C"},
          "action_items": []}),
        ("cost-report",
         {"session_id": "s1", "total_input_tokens": 0, "total_output_tokens": 0,
          "total_tokens": 0, "total_estimated_cost_usd": 0.0,
          "per_node": [], "models_used": []}),
        ("session-meta", {"thread_id": "t-1"}),
        ("llm-call",
         {"call_id": "c1", "timestamp": "2026-07-12T12:00:00",
          "node_name": "analysis", "model": "gpt-4o",
          "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
          "latency_ms": 0}),
    ]

    @pytest.mark.parametrize(("schema_name", "valid_data"), _VALID_SCHEMAS)
    def test_valid_schema(self, schema_name: str, valid_data: dict) -> None:
        """Each of the 16 schemas accepts a valid sample dict."""
        assert validate_input(valid_data, schema_name) is True

    _INVALID_SCHEMAS = [
        ("alert",
         {"service": "pay", "summary": "err",
          "timestamp": "2026-07-12T12:00:00"},
         "severity"),
        ("chat-message",
         {"author": "alice", "text": "hello"},
         "timestamp"),
        ("log-entry",
         {"level": "ERROR", "message": "boom"},
         "timestamp"),
        ("github-pr",
         {"title": "fix", "author": "bob",
          "merge_time": "2026-07-12T12:00:00"},
         "number"),
        ("runbook",
         {"content": "## Triage"},
         "title"),
        ("incident-meta",
         {"service": "pay", "severity": "SEV1",
          "start_time": "2026-07-12T12:00:00"},
         "incident_id"),
        ("incident-input", {}, "alert"),
        ("incident-result", {}, "thread_id"),
        ("timeline-event",
         {"source": "alert", "event_type": "fired",
          "content": "test", "trust_level": "high"},
         "timestamp"),
        ("deploy-correlation",
         {"pr_title": "fix", "author": "bob",
          "merge_time": "2026-07-12T12:00:00", "minutes_before_alert": 10},
         "pr_number"),
        ("stakeholder-update",
         {"impact": "x", "root_cause_hypothesis": "y", "action": "z",
          "next_update_time": "2026-07-12T12:00:00",
          "timestamp": "2026-07-12T12:00:00"},
         "update_number"),
        ("remediation-suggestion",
         {"citation": "runbook.md", "confidence": 0.8},
         "action"),
        ("postmortem",
         {"incident_date": "2026-07-12T12:00:00", "severity": "SEV1",
          "service": "pay",
          "summary": {"title": "S", "content": "C"},
          "timeline": {"title": "T", "content": "C"},
          "root_cause_analysis": {"title": "R", "content": "C"},
          "systemic_contributing_factors": {"title": "S", "content": "C"},
          "action_items": []},
         "incident_id"),
        ("cost-report",
         {"session_id": "s1", "total_input_tokens": 0,
          "total_output_tokens": 0, "total_estimated_cost_usd": 0.0,
          "per_node": [], "models_used": []},
         "total_tokens"),
        ("session-meta", {}, "thread_id"),
        ("llm-call",
         {"timestamp": "2026-07-12T12:00:00", "node_name": "analysis",
          "model": "gpt-4o", "input_tokens": 0, "output_tokens": 0,
          "total_tokens": 0, "latency_ms": 0},
         "call_id"),
    ]

    @pytest.mark.parametrize(
        ("schema_name", "invalid_data", "missing_field"), _INVALID_SCHEMAS
    )
    def test_invalid_schema_missing_field(
        self, schema_name: str, invalid_data: dict, missing_field: str
    ) -> None:
        """Each of the 16 schemas raises ValidationError for a missing required field."""
        with pytest.raises(ValidationError):
            validate_input(invalid_data, schema_name)
