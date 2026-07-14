"""Tests for the log_parser module: parse_log_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from incident_commander.ingest.log_parser import (
    _parse_json_log,
    _parse_markdown_log,
    _parse_timestamp,
    parse_log_file,
)


class TestParseLogFile:
    """parse_log_file — parses .log, .json, .md formats."""

    def test_standard_log_format(self, tmp_path: Path) -> None:
        """.log file with standard format parses correctly."""
        # ISO timestamp + level + source: message — the canonical format from most logging systems
        file = tmp_path / "app.log"
        file.write_text("2026-07-13T14:05:00 ERROR payment-service: Connection pool exhausted\n"
                        "2026-07-13T14:06:00 INFO  payment-service: Retrying connection\n")
        result = parse_log_file(file)
        assert len(result) == 2
        assert result[0].level == "ERROR"
        assert "pool exhausted" in result[0].message
        assert result[0].source == "payment-service"
        assert isinstance(result[0].timestamp, object)

    def test_json_format(self, tmp_path: Path) -> None:
        """.json file with log array parses correctly."""
        file = tmp_path / "logs.json"
        file.write_text('[{"timestamp": "2026-07-13T14:05:00", "level": "ERROR", '
                        '"message": "fail", "source": "srv"}]')
        result = parse_log_file(file)
        assert len(result) == 1
        assert result[0].level == "ERROR"

    def test_markdown_format(self, tmp_path: Path) -> None:
        """.md file with log code blocks parses correctly."""
        file = tmp_path / "incident.md"
        file.write_text("## Logs\n```\n2026-07-13T14:05:00 WARN api-gateway: high latency\n```\n")
        result = parse_log_file(file)
        assert len(result) == 1
        assert result[0].level == "WARN"

    def test_unknown_extension_returns_empty(self, tmp_path: Path) -> None:
        """Unknown file extension returns empty list."""
        # .txt is not .log/.json/.md — parser returns [] without crashing
        file = tmp_path / "data.txt"
        file.write_text("some content")
        assert parse_log_file(file) == []

    def test_file_not_found_raises(self) -> None:
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_log_file("/nonexistent/log.log")

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        """Lines not matching the expected pattern are skipped."""
        # First line has no timestamp — parser must skip it silently, not crash
        file = tmp_path / "messy.log"
        file.write_text("garbage line\n2026-07-13T14:05:00 ERROR svc: real error\n")
        result = parse_log_file(file)
        assert len(result) == 1


class TestParseTimestamp:
    """_parse_timestamp — individual timestamp parsing."""

    def test_unix_epoch(self) -> None:
        """Unix epoch seconds parse to datetime."""
        ts = _parse_timestamp("1752412800")
        assert ts is not None
        assert ts.year == 2025
        assert ts.month == 7
        assert ts.day == 13

    def test_slash_date(self) -> None:
        """Slash-separated date + time parses correctly."""
        ts = _parse_timestamp("2026/07/13 14:05:00")
        assert ts is not None
        assert ts.year == 2026
        assert ts.month == 7
        assert ts.day == 13
        assert ts.hour == 14
        assert ts.minute == 5

    def test_invalid_returns_none(self) -> None:
        """Invalid string returns None."""
        assert _parse_timestamp("invalid") is None


class TestParseJsonLog:
    """_parse_json_log — JSON log parsing edge cases."""

    def test_malformed_json_returns_empty(self) -> None:
        """Malformed JSON returns empty list."""
        result = _parse_json_log("[{invalid json}", "test.json")
        assert result == []

    def test_mixed_valid_invalid(self) -> None:
        """Valid entries pass through; invalid ones are skipped."""
        raw = (
            '[{"timestamp":"2026-01-01T00:00:00","level":"INFO","message":"ok"},'
            '{"level":"BOGUS"}]'
        )
        result = _parse_json_log(raw, "test.json")
        assert len(result) == 1
        assert result[0].message == "ok"

    def test_source_fallback(self) -> None:
        """Entry without source field gets file path as source."""
        raw = '[{"timestamp":"2026-01-01T00:00:00","level":"INFO","message":"hi"}]'
        result = _parse_json_log(raw, "/path/to/logs.json")
        assert len(result) == 1
        assert result[0].source == "/path/to/logs.json"


class TestParseMarkdownLog:
    """_parse_markdown_log — code block extraction."""

    def test_code_block_with_language_tag(self) -> None:
        """Code block with python language tag extracts content."""
        raw = "```python\n2026-01-01T00:00:00 ERROR svc: oops\n```"
        result = _parse_markdown_log(raw)
        assert len(result) == 1
        assert result[0].level == "ERROR"

    def test_multiple_code_blocks(self) -> None:
        """Multiple code blocks are all extracted."""
        raw = (
            "```\n2026-01-01T00:00:00 ERROR svc: first\n```\n"
            "some text\n"
            "```\n2026-01-01T00:00:01 WARN  svc: second\n```\n"
        )
        result = _parse_markdown_log(raw)
        assert len(result) == 2
        assert "first" in result[0].message
        assert "second" in result[1].message
