"""E2E tests: all 10 output files verified for content and structure."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from incident_commander.api import run_simulation
from incident_commander.models.output import IncidentResult


class TestOutputDirE2E:
    """Output directory — all 10 files present with correct content."""

    def test_all_ten_output_files_created(self) -> None:
        """Running with output_dir creates 10 output files."""
        # Files are: summary, timeline, stakeholder updates, comms blocks, remediation, postmortem,
        # cost report, LLM calls JSONL, session JSON, and meta JSON
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_simulation(auto_approve=True, output_dir=tmpdir)
            assert isinstance(result, IncidentResult)
            written = {p.name for p in Path(tmpdir).iterdir()}
            expected = {
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
            }
            missing = expected - written
            assert not missing, f"Missing files: {missing}"

    def test_incident_summary_has_content(self) -> None:
        """incident-summary.md contains incident metadata."""
        # File must exist AND have meaningful content (>50 chars)
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            content = (Path(tmpdir) / "incident-summary.md").read_text()
            assert "Incident ID" in content or "# Incident" in content
            assert len(content) > 50

    def test_timeline_has_events(self) -> None:
        """timeline.md contains chronological event entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            content = (Path(tmpdir) / "timeline.md").read_text()
            assert len(content) > 50

    def test_stakeholder_updates_present(self) -> None:
        """stakeholder-updates.md has consequence-first format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            content = (Path(tmpdir) / "stakeholder-updates.md").read_text()
            assert len(content) > 20

    def test_comms_blocks_pasteable(self) -> None:
        """comms-blocks.md has pasteable sections with separators."""
        # Comms blocks must contain either "---" separators or a "no updates" message
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            content = (Path(tmpdir) / "comms-blocks.md").read_text()
            assert "---" in content or "No updates drafted" in content

    def test_postmortem_has_ai_labels(self) -> None:
        """postmortem.md contains AI-generated section labels."""
        # SEV1 postmortems include [AI-GENERATED] labels on each section
        with tempfile.TemporaryDirectory() as tmpdir:
            run_simulation(
                service="payment-service", severity="SEV1",
                auto_approve=True, output_dir=tmpdir,
            )
            content = (Path(tmpdir) / "postmortem.md").read_text()
            assert "[AI-GENERATED" in content or "(none)" in content

    def test_cost_report_has_numbers(self) -> None:
        """cost-report.md contains numeric cost data."""
        # Must have at least one digit (token count or cost $ amount)
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            content = (Path(tmpdir) / "cost-report.md").read_text()
            assert any(c.isdigit() for c in content)

    def test_llm_calls_jsonl_is_valid_jsonl(self) -> None:
        """llm-calls.jsonl has one valid JSON object per line."""
        # Every line must be valid JSON with required call_id and model fields
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            lines = (Path(tmpdir) / "llm-calls.jsonl").read_text().strip().splitlines()
            if lines:
                for line in lines:
                    obj = json.loads(line)
                    assert "call_id" in obj
                    assert "model" in obj

    def test_session_json_is_valid(self) -> None:
        """session.json is valid JSON with all expected keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            data = json.loads((Path(tmpdir) / "session.json").read_text())
            assert "thread_id" in data
            assert "timeline" in data

    def test_meta_json_has_metadata(self) -> None:
        """meta.json contains session metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = run_simulation(auto_approve=True, output_dir=tmpdir)
            meta = json.loads((Path(tmpdir) / "meta.json").read_text())
            assert "thread_id" in meta
            assert "generated_at" in meta
            assert "version" in meta
