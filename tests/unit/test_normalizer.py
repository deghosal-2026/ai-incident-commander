"""Tests for the normalizer module: _normalize_alert, _normalize_logs, etc."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incident_commander.ingest.normalizer import (
    _load_json_dir,
    _normalize_alert,
    _normalize_github,
    _normalize_logs,
    _normalize_messages,
    _normalize_runbooks,
    _read_json,
    normalize,
)
from incident_commander.models.input import Runbook
from incident_commander.models.state import Alert, ChatMessage, GitHubPR, LogEntry


class TestNormalizeAlert:
    """_normalize_alert — from Alert, dict, or file path."""

    def test_alert_object_passthrough(self) -> None:
        """Alert object passed through unchanged."""
        # `is` identity check — must return the exact same object, not a copy
        alert = Alert(severity="SEV1", service="test", summary="test", timestamp=datetime.now())
        result = _normalize_alert(alert)
        assert result is alert

    def test_alert_dict_converted(self) -> None:
        """Dict with valid fields converts to Alert."""
        ts = datetime.now()
        result = _normalize_alert({
            "severity": "SEV1", "service": "srv", "summary": "err", "timestamp": ts,
        })
        assert isinstance(result, Alert)
        assert result.severity == "SEV1"
        assert result.service == "srv"

    def test_alert_json_file_path(self, tmp_path: Path) -> None:
        """Path to JSON file reads and converts to Alert."""
        # str path (not Path object) to verify the overload accepting string paths works
        ts = datetime.now().isoformat()
        file = tmp_path / "alert.json"
        file.write_text(json.dumps({
            "severity": "SEV2", "service": "srv", "summary": "err", "timestamp": ts,
        }))
        result = _normalize_alert(str(file))
        assert isinstance(result, Alert)
        assert result.severity == "SEV2"

    def test_alert_invalid_type_raises(self) -> None:
        """Invalid type (int) raises TypeError."""
        # int is not Alert, dict, Path, or str — must raise TypeError
        with pytest.raises(TypeError):
            _normalize_alert(42)  # type: ignore[arg-type]

    def test_alert_missing_field_raises(self) -> None:
        """Dict missing required field raises ValidationError."""
        # severity alone is not enough — service, summary, timestamp all required
        with pytest.raises(ValidationError):
            _normalize_alert({"severity": "SEV1"})


class TestNormalizeLogs:
    """_normalize_logs — from list, dict, file path, or None."""

    def test_none_returns_empty(self) -> None:
        """None input returns empty list."""
        # Normalizers must handle None gracefully (field wasn't provided in input)
        assert _normalize_logs(None) == []

    def test_log_entry_list_passthrough(self) -> None:
        """List of LogEntry objects passes through."""
        entries = [LogEntry(timestamp=datetime.now(), level="ERROR", message="fail")]
        result = _normalize_logs(entries)
        assert result == entries

    def test_dict_list_converted(self) -> None:
        """List of dicts converts to LogEntry list."""
        # ISO string timestamps in dicts must be parsed into datetime objects
        ts = datetime.now().isoformat()
        result = _normalize_logs([{"timestamp": ts, "level": "WARN", "message": "warn"}])
        assert len(result) == 1
        assert isinstance(result[0], LogEntry)
        assert result[0].level == "WARN"

    def test_invalid_type_in_list_raises(self) -> None:
        """List with non-dict, non-LogEntry raises TypeError."""
        # Raw ints inside the list are not acceptable types
        with pytest.raises(TypeError):
            _normalize_logs([42])  # type: ignore[arg-type]

    def test_invalid_type_raises(self) -> None:
        """Non-list, non-string type raises TypeError."""
        with pytest.raises(TypeError):
            _normalize_logs(99)  # type: ignore[arg-type]

    def test_file_not_found_raises(self) -> None:
        """Non-existent file path raises FileNotFoundError."""
        # Path object pointing to non-existent file must raise, not silently return []
        with pytest.raises(FileNotFoundError):
            _normalize_logs(Path("/nonexistent/logs.json"))


class TestNormalizeMessages:
    """_normalize_messages — from list, dict, file, or None."""

    def test_none_returns_empty(self) -> None:
        """None input returns empty list."""
        assert _normalize_messages(None) == []

    def test_chat_message_list_passthrough(self) -> None:
        """List of ChatMessage objects passes through."""
        msgs = [ChatMessage(timestamp=datetime.now(), author="alice", text="hello")]
        result = _normalize_messages(msgs)
        assert result == msgs

    def test_dict_list_converted(self) -> None:
        """List of dicts converts to ChatMessage list."""
        # channel is optional — missing channel should not cause validation error
        ts = datetime.now().isoformat()
        result = _normalize_messages([{"timestamp": ts, "author": "bob", "text": "hi"}])
        assert len(result) == 1
        assert result[0].author == "bob"

    def test_invalid_type_raises(self) -> None:
        """Non-list type raises TypeError."""
        with pytest.raises(TypeError):
            _normalize_messages(42)  # type: ignore[arg-type]


class TestNormalizeGitHub:
    """_normalize_github — from list, dict, file, or None."""

    def test_none_returns_empty(self) -> None:
        """None input returns empty list."""
        assert _normalize_github(None) == []

    def test_github_pr_list_passthrough(self) -> None:
        """List of GitHubPR objects passes through."""
        prs = [GitHubPR(number=1, title="fix", author="alice", merge_time=datetime.now())]
        result = _normalize_github(prs)
        assert result == prs

    def test_dict_list_converted(self) -> None:
        """List of dicts converts to GitHubPR list."""
        ts = datetime.now().isoformat()
        result = _normalize_github([
            {"number": 42, "title": "fix", "author": "bob", "merge_time": ts},
        ])
        assert len(result) == 1
        assert result[0].number == 42

    def test_invalid_type_raises(self) -> None:
        """Non-list, non-string type raises TypeError."""
        with pytest.raises(TypeError):
            _normalize_github(99)  # type: ignore[arg-type]


class TestNormalizeRunbooks:
    """_normalize_runbooks — from list, dict, or None."""

    def test_none_returns_empty(self) -> None:
        """None input returns empty list."""
        assert _normalize_runbooks(None) == []

    def test_runbook_list_passthrough(self) -> None:
        """List of Runbook objects passes through."""
        rbs = [Runbook(title="rb1", content="steps")]
        result = _normalize_runbooks(rbs)
        assert result == rbs

    def test_dict_list_converted(self) -> None:
        """List of dicts converts to Runbook list."""
        result = _normalize_runbooks([{"title": "rb1", "content": "steps"}])
        assert len(result) == 1
        assert result[0].title == "rb1"

    def test_invalid_type_raises(self) -> None:
        """Non-list type raises TypeError."""
        with pytest.raises(TypeError):
            _normalize_runbooks("bad")  # type: ignore[arg-type]


class TestNormalize:
    """normalize() — public entry point."""

    def test_normalize_public_entry(self) -> None:
        """Call normalize() with a dict alert and verify return structure."""
        result = normalize(alert={
            "severity": "SEV1", "service": "x", "summary": "test",
            "source": "s", "timestamp": "2026-01-01T00:00:00",
        })
        assert isinstance(result, dict)
        assert set(result) == {"alert", "logs", "messages", "github", "runbooks"}
        assert isinstance(result["alert"], Alert)
        assert isinstance(result["logs"], list)
        assert isinstance(result["messages"], list)
        assert isinstance(result["github"], list)


class TestReadJson:
    """_read_json — low-level JSON file reader."""

    def test_file_not_found(self) -> None:
        """Non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            _read_json("/nonexistent/path.json")


class TestNormalizeAlertNonDict:
    """_normalize_alert — non-dict JSON file."""

    def test_non_dict_json_file(self, tmp_path: Path) -> None:
        """JSON file containing an array raises TypeError."""
        file = tmp_path / "alert.json"
        file.write_text("[]")
        with pytest.raises(TypeError, match="Expected a dict"):
            _normalize_alert(str(file))


class TestNormalizeLogsNonList:
    """_normalize_logs — non-list JSON file."""

    def test_non_list_json_file(self, tmp_path: Path) -> None:
        """JSON file containing a dict raises TypeError."""
        file = tmp_path / "logs.json"
        file.write_text("{}")
        with pytest.raises(TypeError, match="Expected a list"):
            _normalize_logs(str(file))


class TestNormalizeMessagesNonList:
    """_normalize_messages — non-list JSON file."""

    def test_non_list_json_file(self, tmp_path: Path) -> None:
        """JSON file containing a dict raises TypeError."""
        file = tmp_path / "messages.json"
        file.write_text("{}")
        with pytest.raises(TypeError, match="Expected a list"):
            _normalize_messages(str(file))


class TestNormalizeGitHubNonList:
    """_normalize_github — non-list JSON file."""

    def test_non_list_json_file(self, tmp_path: Path) -> None:
        """JSON file containing a dict raises TypeError."""
        file = tmp_path / "github.json"
        file.write_text("{}")
        with pytest.raises(TypeError, match="Expected a list"):
            _normalize_github(str(file))


class TestLoadJsonDir:
    """_load_json_dir — loads all JSON files from a directory."""

    def test_load_list(self, tmp_path: Path) -> None:
        """File containing a list yields its entries."""
        d = tmp_path / "logs"
        d.mkdir()
        (d / "file1.json").write_text(json.dumps([{"a": 1}, {"a": 2}]))
        result = _load_json_dir(str(d))
        assert result == [{"a": 1}, {"a": 2}]

    def test_load_dict(self, tmp_path: Path) -> None:
        """File containing a dict yields a single-entry list."""
        d = tmp_path / "configs"
        d.mkdir()
        (d / "cfg.json").write_text(json.dumps({"key": "val"}))
        result = _load_json_dir(str(d))
        assert result == [{"key": "val"}]

    def test_nonexistent_dir_raises(self) -> None:
        """Non-existent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            _load_json_dir("/nonexistent/dir")
