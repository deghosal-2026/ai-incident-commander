"""Tests for MarkdownOutputWriter — writes incident output to disk."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from incident_commander.models.output import IncidentResult
from incident_commander.models.state import (
    ActionItem,
    CostReport,
    DeployCorrelation,
    NodeCost,
    Postmortem,
    PostmortemSection,
    RemediationSuggestion,
    StakeholderUpdate,
    TimelineEvent,
)
from incident_commander.output.markdown_writer import MarkdownOutputWriter
from tests.conftest import NOW


class TestMarkdownOutputWriter:
    """MarkdownOutputWriter.write_all — produces 10 output files."""

    def _make_result(self) -> IncidentResult:
        return IncidentResult(
            thread_id="test-thread-001",
            timeline=[
                TimelineEvent(
                    timestamp=NOW,
                    source="alert",
                    event_type="trigger",
                    content="DB pool exhausted",
                    trust_level="high",
                ),
            ],
            stakeholder_updates=[
                StakeholderUpdate(
                    update_number=1,
                    impact="Payment failures",
                    root_cause_hypothesis="DB pool",
                    action="Rollback",
                    next_update_time=NOW,
                    confidence=0.85,
                    approved=True,
                    timestamp=NOW,
                ),
            ],
            remediation_suggestions=[
                RemediationSuggestion(
                    action="Scale up",
                    citation="runbook/scale.md",
                    confidence=0.9,
                    dry_run_outcome="",
                    similar_incidents=[],
                    approved=False,
                ),
            ],
            deploy_correlations=[
                DeployCorrelation(
                    pr_number=42,
                    pr_title="Fix pool settings",
                    author="bob",
                    merge_time=NOW,
                    minutes_before_alert=5,
                    correlation_strength="strong",
                ),
            ],
            postmortem=Postmortem(
                incident_id="INC-001",
                incident_date=NOW,
                severity="SEV1",
                service="payment-service",
                summary=PostmortemSection(title="Summary", content="DB outage"),
                timeline=PostmortemSection(title="Timeline", content="Events"),
                root_cause_analysis=PostmortemSection(
                    title="Root Cause", content="Pool exhausted",
                ),
                systemic_contributing_factors=PostmortemSection(
                    title="Systemic", content="No circuit breaker",
                ),
                action_items=[
                    ActionItem(
                        description="Add circuit breaker",
                        suggested_owner="DB team",
                        priority="P0",
                    ),
                ],
                customer_impact=PostmortemSection(
                    title="Customer Impact", content="5% failures",
                ),
                stakeholder_communication_log=PostmortemSection(
                    title="Comm Log", content="Updates at 12:05",
                ),
                regulatory_compliance_impact=PostmortemSection(
                    title="Regulatory Impact", content="None",
                ),
                resolved_at=NOW,
                mttr_minutes=15,
            ),
            cost_report=CostReport(
                session_id="s1",
                total_input_tokens=500,
                total_output_tokens=300,
                total_tokens=800,
                total_estimated_cost_usd=0.001,
                per_node=[
                    NodeCost(
                        node_name="draft_update",
                        llm_model="gpt-4o",
                        input_tokens=400,
                        output_tokens=200,
                        total_tokens=600,
                        estimated_cost_usd=0.001,
                        latency_ms=500,
                    ),
                ],
                models_used=["gpt-4o"],
            ),
        )

    def test_write_all_creates_ten_files(self) -> None:
        """write_all creates all 10 expected output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._make_result()
            writer = MarkdownOutputWriter(tmpdir)
            files = writer.write_all(result)
            assert len(files) == 10
            created = [Path(p).name for p in files]
            expected = [
                "incident-summary.md",
                "timeline.md",
                "stakeholder-updates.md",
                "comms-blocks.md",
                "remediation.md",
                "postmortem.md",
                "cost-report.md",
                "llm-calls.jsonl",
                "session.json",
                "meta.json",
            ]
            for name in expected:
                assert name in created, f"Missing file: {name}"
            for f in files:
                assert f.exists()

    def test_write_all_content_non_empty(self) -> None:
        """All generated files have content (llm-calls.jsonl may be empty)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._make_result()
            writer = MarkdownOutputWriter(tmpdir)
            writer.write_all(result)
            for f in Path(tmpdir).iterdir():
                text = f.read_text()
                if f.name == "llm-calls.jsonl":
                    continue
                assert len(text) > 0, f"Empty file: {f.name}"

    def test_oserror_on_write(self) -> None:
        """OSError is raised when the output directory is read-only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "readonly"
            out_dir.mkdir()
            original_mode = out_dir.stat().st_mode
            os.chmod(out_dir, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            try:
                result = self._make_result()
                writer = MarkdownOutputWriter(out_dir)
                import pytest
                with pytest.raises(OSError):
                    writer.write_all(result)
            finally:
                os.chmod(out_dir, original_mode)
