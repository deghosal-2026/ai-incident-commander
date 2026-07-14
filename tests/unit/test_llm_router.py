"""Tests for the llm_router module: LLMRouter, CostTracker, LLMObserver."""

from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path
from typing import Any

import pytest

import incident_commander.nodes._llm as _llm_module
from incident_commander.config import Config, LLMConfig
from incident_commander.llm_router import CostTracker, LLMObserver, LLMRouter
from incident_commander.nodes._llm import get_llm_router


def _mock_llm(prompt: str, model: str) -> tuple[str, dict[str, Any]]:
    """Mock LLM that returns a canned response."""
    return ("mock response", {"input_tokens": 10, "output_tokens": 20})


class TestCostTracker:
    """CostTracker — accumulates per-node token/cost data."""

    def test_record_then_report(self) -> None:
        """Recording 3 calls returns correct aggregates."""
        # Mixed models and nodes — verifies aggregation across dimensions
        ct = CostTracker()
        ct.record_call("analysis", "gpt-4o", 100, 50, 0.001, 200)
        ct.record_call("comms", "gpt-4o-mini", 50, 25, 0.0002, 100)
        ct.record_call("analysis", "gpt-4o", 200, 100, 0.002, 300)
        report = ct.get_report("session-1")
        assert report.session_id == "session-1"
        assert report.total_input_tokens == 350
        assert report.total_output_tokens == 175
        assert report.total_tokens == 525
        assert len(report.per_node) == 3

    def test_total_tokens_sum(self) -> None:
        """total_tokens equals input + output."""
        # Verifies the invariant: total = input + output for a single call
        ct = CostTracker()
        ct.record_call("analysis", "gpt-4o", 100, 50, 0.0, 0)
        report = ct.get_report()
        assert report.total_tokens == report.total_input_tokens + report.total_output_tokens

    def test_zero_calls(self) -> None:
        """Zero calls produces empty CostReport with zeros."""
        # Empty tracker must not crash — returns zero-filled report
        ct = CostTracker()
        report = ct.get_report("empty")
        assert report.total_tokens == 0
        assert report.total_estimated_cost_usd == 0.0
        assert report.per_node == []
        assert report.models_used == []


class TestLLMObserver:
    """LLMObserver — logs calls to JSONL."""

    def test_logs_to_jsonl(self, tmp_path: Path) -> None:
        """Logging 3 calls produces 3 JSONL lines."""
        # Each log_call -> one line in the JSONL file (one JSON object per line)
        obs = LLMObserver(log_dir=str(tmp_path))
        for i in range(3):
            obs.log_call(f"call-{i}", "analysis", "gpt-4o", 10, 20, 0.001, 100)
        log_file = tmp_path / "llm-calls.jsonl"
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_log_line_has_required_fields(self, tmp_path: Path) -> None:
        """Each JSONL line has all required fields."""
        # JSONL record must include all tracked dimensions for auditability
        obs = LLMObserver(log_dir=str(tmp_path))
        obs.log_call("call-1", "analysis", "gpt-4o", 10, 20, 0.001, 100)
        log_file = tmp_path / "llm-calls.jsonl"
        record = json.loads(log_file.read_text().strip())
        assert "call_id" in record
        assert "node_name" in record
        assert "model" in record
        assert "input_tokens" in record
        assert "output_tokens" in record
        assert "timestamp" in record

    def test_prompt_hash_sha256(self, tmp_path: Path) -> None:
        """prompt_hash is a SHA-256 hex string."""
        # Prompts are hashed (not stored raw) for privacy — 64 hex chars = SHA-256
        obs = LLMObserver(log_dir=str(tmp_path))
        obs.log_call("c1", "analysis", "gpt-4o", 0, 0, 0, 0, prompt="test prompt")
        log_file = tmp_path / "llm-calls.jsonl"
        record = json.loads(log_file.read_text().strip())
        assert len(record["prompt_hash"]) == 64

    def test_log_dir_created(self, tmp_path: Path) -> None:
        """Log directory is created if it does not exist."""
        # Deeply nested log_dir must be created on first write, not fail
        log_dir = tmp_path / "new" / "logs"
        obs = LLMObserver(log_dir=str(log_dir))
        obs.log_call("c1", "analysis", "gpt-4o", 0, 0, 0, 0)
        assert log_dir.exists()


class TestLLMRouter:
    """LLMRouter — routes calls to the correct model."""

    def test_analysis_routes_to_analysis_model(self) -> None:
        """Analysis task uses the analysis model."""
        # Default config uses local Ollama model — no cloud API costs
        router = LLMRouter(mock_llm=_mock_llm)
        response, info = router.generate("diagnose", task="analysis")
        assert info["model"] == "ollama/qwen2.5-coder:7b"

    def test_comms_falls_back_to_analysis(self) -> None:
        """Comms task falls back to analysis model when not configured."""
        # When comms_model is None, the analysis model is used as the fallback
        router = LLMRouter(mock_llm=_mock_llm)
        _, info = router.generate("write update", task="comms")
        assert info["model"] == "ollama/qwen2.5-coder:7b"

    def test_postmortem_falls_back_to_analysis(self) -> None:
        """Postmortem task falls back to analysis model when not configured."""
        router = LLMRouter(mock_llm=_mock_llm)
        _, info = router.generate("write pm", task="postmortem")
        assert info["model"] == "ollama/qwen2.5-coder:7b"

    def test_comms_uses_explicit_model(self) -> None:
        """Comms task uses explicit comms_model when configured."""
        # Custom LLMConfig with dedicated comms model overrides the fallback
        cfg = Config(llm=LLMConfig(comms_model="gpt-4o-mini"))
        router = LLMRouter(config=cfg, mock_llm=_mock_llm)
        _, info = router.generate("write update", task="comms")
        assert info["model"] == "gpt-4o-mini"

    def test_model_override_bypasses_routing(self) -> None:
        """model_override bypasses task-based routing."""
        # model_override takes precedence over all task-based routing
        router = LLMRouter(mock_llm=_mock_llm)
        _, info = router.generate("diagnose", task="analysis", model_override="claude-3-5-sonnet")
        assert info["model"] == "claude-3-5-sonnet"

    def test_mock_llm_returns_configured_response(self) -> None:
        """Mock LLM returns the configured response."""
        router = LLMRouter(mock_llm=_mock_llm)
        response, _ = router.generate("hello")
        assert response == "mock response"

    def test_cost_tracker_integrated(self) -> None:
        """Router's cost tracker records calls automatically."""
        # Every generate() call auto-records into the router's cost_tracker
        router = LLMRouter(mock_llm=_mock_llm)
        router.generate("test prompt", task="analysis")
        report = router.cost_tracker.get_report()
        assert report.total_tokens > 0

    def test_observer_integrated(self, tmp_path: Path) -> None:
        """Router's observer logs calls to JSONL."""
        # When log_dir is configured, generate() also writes to JSONL
        cfg = Config(log_dir=str(tmp_path))
        router = LLMRouter(config=cfg, mock_llm=_mock_llm)
        router.generate("test prompt", task="analysis")
        log_file = tmp_path / "llm-calls.jsonl"
        assert log_file.exists()


class TestGetLLMRouter:
    """get_llm_router — module-level singleton access."""

    def test_before_init_raises_runtime_error(self) -> None:
        """Calling get_llm_router before init raises RuntimeError."""
        _llm_module._router = None  # reset module-level singleton
        with pytest.raises(RuntimeError, match="not initialized"):
            get_llm_router()


class TestLLMObserverDiskFailure:
    """LLMObserver — graceful degradation on write failures."""

    def test_disk_failure_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """log_call does not raise when log dir is read-only; logs a warning."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        os.chmod(str(log_dir), stat.S_IRUSR | stat.S_IXUSR)
        obs = LLMObserver(log_dir=str(log_dir))
        caplog.set_level(logging.WARNING)
        try:
            obs.log_call("c1", "analysis", "gpt-4o", 10, 20, 0.001, 100)
            assert "Failed to write LLM call log" in caplog.text
        finally:
            os.chmod(str(log_dir), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)


class TestModelPricing:
    """LLMRouter — model pricing estimation."""

    def test_empty_pricing_returns_zero(self) -> None:
        """Empty model_pricing dict results in zero cost."""
        cfg = Config(llm=LLMConfig(model_pricing={}))
        router = LLMRouter(config=cfg, mock_llm=_mock_llm)
        _, info = router.generate("test", task="analysis")
        assert info["estimated_cost_usd"] == 0.0

    def test_custom_pricing(self) -> None:
        """Custom model_pricing produces correct cost estimate."""
        def _custom_mock(prompt: str, task: str) -> tuple[str, dict[str, Any]]:
            return ("response", {"input_tokens": 100, "output_tokens": 50})
        cfg = Config(
            llm=LLMConfig(
                model_pricing={"my-model": {"input": 1.0, "output": 2.0}},
                analysis_model="my-model",
            )
        )
        router = LLMRouter(config=cfg, mock_llm=_custom_mock)
        _, info = router.generate("test", task="analysis")
        expected = round((100 / 1_000_000 * 1.0) + (50 / 1_000_000 * 2.0), 6)
        assert info["estimated_cost_usd"] == expected

    def test_unknown_model_defaults_to_free(self) -> None:
        """Unknown model name defaults to zero cost."""
        cfg = Config(llm=LLMConfig(analysis_model="unknown-model"))
        router = LLMRouter(config=cfg, mock_llm=_mock_llm)
        _, info = router.generate("test", task="analysis")
        assert info["estimated_cost_usd"] == 0.0
