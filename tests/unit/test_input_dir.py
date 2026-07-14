"""Tests for the input_dir module: InputDirLoader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from incident_commander.ingest.input_dir import InputDirLoader
from incident_commander.models.input import IncidentInput


class TestInputDirLoader:
    """InputDirLoader — loads structured incident directories."""

    def _write_meta(self, directory: Path) -> None:
        """Write a minimal meta.json fixture file."""
        (directory / "meta.json").write_text(json.dumps({
            "incident_id": "INC-001", "service": "test-svc",
            "severity": "SEV1", "start_time": "2026-07-13T14:00:00",
        }))

    def _write_alert(self, directory: Path) -> None:
        """Write a minimal alert.json fixture file."""
        (directory / "alert.json").write_text(json.dumps({
            "severity": "SEV1", "service": "test-svc",
            "summary": "test alert", "timestamp": "2026-07-13T14:00:00",
        }))

    def test_full_directory(self, tmp_path: Path) -> None:
        """Full directory produces valid IncidentInput."""
        # Full happy path: every optional file/directory present
        self._write_meta(tmp_path)
        self._write_alert(tmp_path)
        (tmp_path / "logs").mkdir()
        (tmp_path / "logs" / "app.log").write_text("2026-07-13T14:05:00 ERROR svc: fail\n")
        (tmp_path / "messages.json").write_text(json.dumps([
            {"timestamp": "2026-07-13T14:01:00", "author": "alice", "text": "seeing errors"},
        ]))
        (tmp_path / "github.json").write_text(json.dumps([
            {"number": 1, "title": "fix", "author": "bob", "merge_time": "2026-07-13T13:50:00"},
        ]))
        (tmp_path / "notes.md").write_text("## 14:05 — Spike\nHigh CPU")
        result = InputDirLoader(tmp_path).load()
        assert isinstance(result, IncidentInput)
        assert result.alert.severity == "SEV1"
        assert result.meta is not None
        assert result.meta.incident_id == "INC-001"

    def test_missing_meta_raises(self, tmp_path: Path) -> None:
        """Missing meta.json raises FileNotFoundError."""
        # meta and alert are required; loader must fail fast with clear error
        self._write_alert(tmp_path)
        with pytest.raises(FileNotFoundError, match="meta.json"):
            InputDirLoader(tmp_path).load()

    def test_missing_alert_raises(self, tmp_path: Path) -> None:
        """Missing alert.json raises FileNotFoundError."""
        self._write_meta(tmp_path)
        with pytest.raises(FileNotFoundError, match="alert.json"):
            InputDirLoader(tmp_path).load()

    def test_missing_optionals_default_empty(self, tmp_path: Path) -> None:
        """Missing optional files result in empty lists."""
        # Only meta.json + alert.json present — all other fields must default to empty lists
        self._write_meta(tmp_path)
        self._write_alert(tmp_path)
        result = InputDirLoader(tmp_path).load()
        assert result.logs == []
        assert result.messages == []
        assert result.github == []
        assert result.runbooks == []
        assert result.manual_events == []

    def test_empty_logs_dir_empty_list(self, tmp_path: Path) -> None:
        """Empty logs/ directory yields empty log list."""
        # logs/ directory exists but contains no files → empty list, not error
        self._write_meta(tmp_path)
        self._write_alert(tmp_path)
        (tmp_path / "logs").mkdir()
        result = InputDirLoader(tmp_path).load()
        assert result.logs == []

    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        """Malformed JSON in alert.json raises JSONDecodeError."""
        self._write_meta(tmp_path)
        (tmp_path / "alert.json").write_text("{invalid}")
        with pytest.raises(json.JSONDecodeError):
            InputDirLoader(tmp_path).load()

    def test_nonexistent_directory_raises(self) -> None:
        """Non-existent directory raises FileNotFoundError."""
        # Absolute path to non-existent dir — must not create directory silently
        with pytest.raises(FileNotFoundError):
            InputDirLoader("/nonexistent/incident").load()

    def test_malformed_messages_json_raises(self, tmp_path: Path) -> None:
        """Malformed messages.json raises JSONDecodeError with file path."""
        self._write_meta(tmp_path)
        self._write_alert(tmp_path)
        (tmp_path / "messages.json").write_text("{invalid}")
        with pytest.raises(json.JSONDecodeError, match="messages.json"):
            InputDirLoader(tmp_path).load()

    def test_malformed_runbook_json_raises(self, tmp_path: Path) -> None:
        """Malformed runbook file raises JSONDecodeError with file path."""
        self._write_meta(tmp_path)
        self._write_alert(tmp_path)
        (tmp_path / "runbooks").mkdir()
        (tmp_path / "runbooks" / "rb.json").write_text("{invalid}")
        with pytest.raises(json.JSONDecodeError, match="rb.json"):
            InputDirLoader(tmp_path).load()

    def test_load_required_json_non_dict_raises(self, tmp_path: Path) -> None:
        """alert.json containing an array raises TypeError."""
        self._write_meta(tmp_path)
        (tmp_path / "alert.json").write_text("[]")
        loader = InputDirLoader(tmp_path)
        with pytest.raises(TypeError, match="Expected a dict"):
            loader.load()

    def test_load_optional_runbooks_single_object(self, tmp_path: Path) -> None:
        """Single runbook dict loaded as list of 1."""
        self._write_meta(tmp_path)
        self._write_alert(tmp_path)
        (tmp_path / "runbooks").mkdir()
        (tmp_path / "runbooks" / "rb.json").write_text(
            json.dumps({"title": "rb1", "content": "steps"})
        )
        result = InputDirLoader(tmp_path).load()
        assert len(result.runbooks) == 1
        assert result.runbooks[0].title == "rb1"

    def test_load_optional_runbooks_array(self, tmp_path: Path) -> None:
        """Runbook array loaded as list of 2."""
        self._write_meta(tmp_path)
        self._write_alert(tmp_path)
        (tmp_path / "runbooks").mkdir()
        (tmp_path / "runbooks" / "rb.json").write_text(
            json.dumps([
                {"title": "rb1", "content": "steps"},
                {"title": "rb2", "content": "more steps"},
            ])
        )
        result = InputDirLoader(tmp_path).load()
        assert len(result.runbooks) == 2
        assert result.runbooks[0].title == "rb1"
        assert result.runbooks[1].title == "rb2"
