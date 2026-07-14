"""E2E tests: input directory loading with real fixture data."""

from __future__ import annotations

from incident_commander.api import run_incident
from incident_commander.ingest.input_dir import InputDirLoader
from incident_commander.models.input import IncidentInput


class TestInputDirE2E:
    """Input directory — full, minimal, partial, error cases."""

    FIXTURE_DIR = "tests/fixtures/incident-2026-001"

    def test_full_input_dir_loads(self) -> None:
        """Full input directory loads all fields into IncidentInput."""
        # Real fixture directory with all expected input files
        loader = InputDirLoader(self.FIXTURE_DIR)
        result = loader.load()
        assert isinstance(result, IncidentInput)
        assert result.alert is not None
        assert result.alert.severity == "SEV1"
        assert len(result.logs) > 0
        assert len(result.messages) > 0
        assert len(result.github) > 0
        assert len(result.runbooks) > 0
        assert len(result.manual_events) > 0
        assert result.meta is not None

    def test_minimal_input_dir_loads(self) -> None:
        """Pre-built minimal dir loads with empty optionals."""
        # Only meta.json + alert.json — all other collections must default to empty
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "meta.json").write_text(
                '{"incident_id":"T1","service":"s",'
                '"severity":"SEV3","start_time":"2026-01-01T00:00:00"}'
            )
            (d / "alert.json").write_text(
                '{"severity":"SEV3","service":"s","summary":"test",'
                '"source":"x","timestamp":"2026-01-01T00:00:00"}'
            )
            loader = InputDirLoader(d)
            result = loader.load()
            assert result.alert is not None
            assert len(result.logs) == 0
            assert len(result.messages) == 0
            assert len(result.github) == 0
            assert len(result.runbooks) == 0
            assert len(result.manual_events) == 0

    def test_input_dir_with_notes(self) -> None:
        """Input dir with notes.md produces manual events."""
        # notes.md → manual_events with source="manual" and trust_level="low"
        loader = InputDirLoader(self.FIXTURE_DIR)
        result = loader.load()
        assert len(result.manual_events) > 0
        for ev in result.manual_events:
            assert ev.source == "manual"
            assert ev.trust_level == "low"

    def test_input_dir_with_runbooks(self) -> None:
        """Input dir with runbooks/ loads runbooks."""
        # runbooks/ directory contains individual runbook JSON files
        loader = InputDirLoader(self.FIXTURE_DIR)
        result = loader.load()
        assert len(result.runbooks) > 0
        assert result.runbooks[0].id == "rb-001"

    def test_missing_input_directory(self) -> None:
        """Non-existent input directory raises FileNotFoundError."""
        # try/except pattern (not pytest.raises) to verify the error path explicitly
        loader = InputDirLoader("/tmp/nonexistent-dir-12345")
        try:
            loader.load()
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_malformed_alert_json(self) -> None:
        """Malformed alert.json in input dir raises JSONDecodeError."""
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "meta.json").write_text(
                '{"incident_id":"T1","service":"s",'
                '"severity":"SEV3","start_time":"2026-01-01T00:00:00"}'
            )
            (d / "alert.json").write_text("{bad json}")
            loader = InputDirLoader(d)
            try:
                loader.load()
                assert False, "Expected JSONDecodeError"
            except json.JSONDecodeError:
                pass

    def test_run_from_input_dir_via_api(self) -> None:
        """run_incident with input dir data produces IncidentResult."""
        # End-to-end: load from disk → pass to API → get valid IncidentResult
        loader = InputDirLoader(self.FIXTURE_DIR)
        incident = loader.load()
        result = run_incident(
            alert=incident.alert,
            logs=incident.logs,
            messages=incident.messages,
            github=incident.github,
            runbooks=incident.runbooks,
            manual_events=incident.manual_events,
            auto_approve=True,
        )
        assert result.thread_id != ""
        assert len(result.timeline) >= 1
