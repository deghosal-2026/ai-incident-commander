"""Tests for the persistence module: SessionManager and _SessionCheckpointer."""

from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path

import pytest

from incident_commander.persistence import SessionManager


class TestSessionCheckpointer:
    """_SessionCheckpointer — get/set checkpoint state."""

    def test_get_missing_returns_empty_dict(self, tmp_path: Path) -> None:
        """get() on a missing thread returns an empty dict."""
        mgr = SessionManager(session_dir=str(tmp_path))
        cp = mgr.get_checkpointer("missing-thread")
        assert cp.get() == {}

    def test_set_then_get(self, tmp_path: Path) -> None:
        """After set(), get() returns the same state."""
        mgr = SessionManager(session_dir=str(tmp_path))
        cp = mgr.get_checkpointer("thread-1")
        cp.set({"key": "value", "count": 42})
        assert cp.get() == {"key": "value", "count": 42}

    def test_different_thread_id_returns_empty(self, tmp_path: Path) -> None:
        """Different thread IDs have isolated state."""
        mgr = SessionManager(session_dir=str(tmp_path))
        cp1 = mgr.get_checkpointer("thread-a")
        cp1.set({"data": "a"})
        cp2 = mgr.get_checkpointer("thread-b")
        assert cp2.get() == {}

    def test_set_writes_correct_file_path(self, tmp_path: Path) -> None:
        """set() writes to <thread_id>.json in the session directory."""
        mgr = SessionManager(session_dir=str(tmp_path))
        cp = mgr.get_checkpointer("my-thread")
        cp.set({"state": "saved"})
        expected_file = tmp_path / "my-thread.json"
        assert expected_file.exists()
        data = json.loads(expected_file.read_text())
        assert data == {"state": "saved"}


class TestSessionManager:
    """SessionManager — save, load, list, delete sessions."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Saved session can be loaded and matches."""
        # Round-trip: dict → JSON on disk → dict back; verifies serialization is lossless
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save_session("thread-1", {"key": "value", "count": 42})
        loaded = mgr.load_session("thread-1")
        assert loaded == {"key": "value", "count": 42}

    def test_export_session(self, tmp_path: Path) -> None:
        """export_session returns the saved state dict."""
        # export_session is load_session with a different name for external consumers
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save_session("thread-1", {"data": "test"})
        exported = mgr.export_session("thread-1")
        assert exported["data"] == "test"

    def test_list_sessions(self, tmp_path: Path) -> None:
        """list_sessions returns all session thread IDs."""
        # Must discover sessions by scanning the directory, not an in-memory index
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save_session("session-a", {})
        mgr.save_session("session-b", {})
        ids = mgr.list_sessions()
        assert "session-a" in ids
        assert "session-b" in ids
        assert len(ids) == 2

    def test_nonexistent_session_raises(self, tmp_path: Path) -> None:
        """Loading a non-existent session raises KeyError."""
        # File-not-found on disk maps to KeyError, not FileNotFoundError
        mgr = SessionManager(session_dir=str(tmp_path))
        with pytest.raises(KeyError, match="nonexistent"):
            mgr.load_session("nonexistent")

    def test_delete_session(self, tmp_path: Path) -> None:
        """Deleted session cannot be loaded again."""
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save_session("to-delete", {"data": 1})
        mgr.delete_session("to-delete")
        with pytest.raises(KeyError):
            mgr.load_session("to-delete")

    def test_delete_nonexistent_raises(self, tmp_path: Path) -> None:
        """Deleting a non-existent session raises KeyError."""
        # Must not silently succeed when deleting something that doesn't exist
        mgr = SessionManager(session_dir=str(tmp_path))
        with pytest.raises(KeyError):
            mgr.delete_session("ghost")

    def test_multiple_sessions_coexist(self, tmp_path: Path) -> None:
        """Multiple sessions coexist without interference."""
        # Sessions are isolated — loading one must not affect another
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save_session("s1", {"a": 1})
        mgr.save_session("s2", {"b": 2})
        assert mgr.load_session("s1")["a"] == 1
        assert mgr.load_session("s2")["b"] == 2

    def test_session_dir_created(self, tmp_path: Path) -> None:
        """Session directory created automatically."""
        # Deeply nested path must be created if it doesn't exist
        session_dir = tmp_path / "new" / "sessions"
        SessionManager(session_dir=str(session_dir))
        assert session_dir.exists()

    def test_save_session_oserror(self, tmp_path: Path) -> None:
        """save_session raises OSError when the directory is read-only."""
        mgr = SessionManager(session_dir=str(tmp_path))
        os.chmod(str(tmp_path), stat.S_IRUSR | stat.S_IXUSR)
        try:
            with pytest.raises(OSError):
                mgr.save_session("oserror-thread", {"key": "value"})
        finally:
            os.chmod(str(tmp_path), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

    def test_load_session_corrupt_json(self, tmp_path: Path) -> None:
        """load_session raises ValueError with 'Corrupt session file' for bad JSON."""
        mgr = SessionManager(session_dir=str(tmp_path))
        corrupt_path = tmp_path / "corrupt.json"
        corrupt_path.write_text("{invalid")
        with pytest.raises(ValueError, match="Corrupt session file"):
            mgr.load_session("corrupt")

    def test_concurrent_sessions(self, tmp_path: Path) -> None:
        """Two threads saving different thread_ids produce both files."""
        mgr = SessionManager(session_dir=str(tmp_path))
        errors: list[Exception] = []

        def saver(thread_id: str, data: dict) -> None:
            try:
                mgr.save_session(thread_id, data)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=saver, args=("concurrent-a", {"x": 1}))
        t2 = threading.Thread(target=saver, args=("concurrent-b", {"y": 2}))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == []
        assert mgr.load_session("concurrent-a") == {"x": 1}
        assert mgr.load_session("concurrent-b") == {"y": 2}

    def test_load_session_oserror(self, tmp_path: Path) -> None:
        """load_session raises OSError when the session file is unreadable."""
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save_session("unreadable", {"data": "test"})
        session_file = tmp_path / "unreadable.json"
        os.chmod(str(session_file), 0o000)
        try:
            with pytest.raises(OSError):
                mgr.load_session("unreadable")
        finally:
            os.chmod(str(session_file), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
