"""Tests for config module: LLMConfig and Config models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

# Import the two pydantic config models under test
from incident_commander.config import Config, LLMConfig


class TestLLMConfig:
    """LLMConfig: model routing configuration."""

    def test_defaults(self) -> None:
        """Default LLMConfig uses OMLX local model."""
        cfg = LLMConfig()
        # Local Ollama model is the default analysis backend
        assert cfg.analysis_model == "ollama/qwen2.5-coder:7b"
        # Default base URL points to local Ollama server
        assert cfg.analysis_base_url == "http://localhost:11434/v1"
        # Comms model is optional — None means reuse analysis model
        assert cfg.comms_model is None
        assert cfg.comms_base_url is None
        # Postmortem model is optional — None means reuse analysis model
        assert cfg.postmortem_model is None
        assert cfg.postmortem_base_url is None

    def test_custom_values(self) -> None:
        """Custom model values override defaults."""
        cfg = LLMConfig(
            # GPT-4o as analysis model (OpenAI hosted)
            analysis_model="gpt-4o",
            analysis_base_url="https://api.openai.com/v1",
            # Cheaper model for comms generation
            comms_model="gpt-4o-mini",
            # Anthropic model for postmortem generation
            postmortem_model="claude-3-5-sonnet",
        )
        assert cfg.analysis_model == "gpt-4o"
        assert cfg.comms_model == "gpt-4o-mini"
        assert cfg.postmortem_model == "claude-3-5-sonnet"

    def test_model_pricing_has_entries(self) -> None:
        """Pricing dict has all expected model entries."""
        cfg = LLMConfig()
        # Local default model must have pricing
        assert "ollama/qwen2.5-coder:7b" in cfg.model_pricing
        # Budget OpenAI model used for comms
        assert "gpt-4o-mini" in cfg.model_pricing
        # Premium OpenAI model used for analysis
        assert "gpt-4o" in cfg.model_pricing
        # Anthropic model used for postmortems
        assert "claude-3-5-sonnet" in cfg.model_pricing


class TestConfig:
    """Config: top-level application configuration."""

    def test_defaults(self) -> None:
        """Default Config has simulate mode with sensible defaults."""
        cfg = Config()
        # Safe default: simulate mode prevents real actions
        assert cfg.mode == "simulate"
        # Actions below 0.7 confidence are filtered out
        assert cfg.confidence_threshold == 0.7
        # Deploys within 30 min before alert are considered correlated
        assert cfg.deploy_correlation_window_minutes == 30
        # Cadence: SEV1 every 5m, SEV2 every 15m, SEV3 every 30m
        assert cfg.cadence == {"SEV1": 5, "SEV2": 15, "SEV3": 30}
        # Markdown is the default output format
        assert cfg.output_format == "markdown"

    def test_custom_values(self) -> None:
        """Custom config values override all defaults."""
        cfg = Config(
            # "run" mode enables real remediation actions
            mode="run",
            # Higher threshold — only very confident actions execute
            confidence_threshold=0.85,
            # Tighter correlation window for faster-moving deploys
            deploy_correlation_window_minutes=15,
            # Slower cadence for less urgent incidents
            cadence={"SEV1": 10, "SEV2": 20, "SEV3": 60},
            # JSON output for machine consumption
            output_format="json",
        )
        assert cfg.mode == "run"
        assert cfg.confidence_threshold == 0.85
        assert cfg.deploy_correlation_window_minutes == 15

    def test_invalid_confidence_threshold_low(self) -> None:
        """Confidence threshold below 0 raises ValidationError."""
        # Boundary: just below the valid range [0.0, 1.0]
        with pytest.raises(ValidationError):
            Config(confidence_threshold=-0.1)

    def test_invalid_confidence_threshold_high(self) -> None:
        """Confidence threshold above 1 raises ValidationError."""
        # Boundary: just above the valid range [0.0, 1.0]
        with pytest.raises(ValidationError):
            Config(confidence_threshold=1.5)

    def test_invalid_mode(self) -> None:
        """Invalid mode value raises ValidationError."""
        # Only "simulate" and "run" are valid modes
        with pytest.raises(ValidationError):
            Config(mode="invalid")

    def test_invalid_window_minutes(self) -> None:
        """Window minutes below 1 raises ValidationError."""
        # Boundary: zero minutes means no correlation window at all
        with pytest.raises(ValidationError):
            Config(deploy_correlation_window_minutes=0)

    def test_cadence_custom_values(self) -> None:
        """Cadence dict accepts custom severity intervals."""
        cfg = Config(cadence={"SEV1": 10, "SEV2": 20, "SEV3": 60})
        assert cfg.cadence["SEV1"] == 10
        assert cfg.cadence["SEV2"] == 20
        assert cfg.cadence["SEV3"] == 60

    def test_llm_config_embedded(self) -> None:
        """Config has a nested LLMConfig with its own defaults."""
        cfg = Config()
        # Nested LLMConfig is auto-instantiated with defaults
        assert isinstance(cfg.llm, LLMConfig)
        # Confirms the nested default uses the local Ollama model
        assert cfg.llm.analysis_model == "ollama/qwen2.5-coder:7b"

    def test_llm_config_custom_embedded(self) -> None:
        """Nested LLMConfig accepts overrides via Config."""
        # Override the nested LLMConfig via Config's llm field
        cfg = Config(llm=LLMConfig(analysis_model="gpt-4o"))
        assert cfg.llm.analysis_model == "gpt-4o"

    def test_qdrant_and_github_defaults(self) -> None:
        """Default qdrant_url and github_token are None; collection is 'runbooks'."""
        cfg = Config()
        assert cfg.qdrant_url is None
        assert cfg.qdrant_collection == "runbooks"
        assert cfg.github_token is None

    def test_session_dir_tilde(self) -> None:
        """session_dir stores tilde path expandable via Path.expanduser()."""
        cfg = Config(session_dir="~/test-sessions")
        assert cfg.session_dir == "~/test-sessions"
        expanded = Path(cfg.session_dir).expanduser()
        assert expanded == Path.home() / "test-sessions"

    def test_log_dir_tilde(self) -> None:
        """log_dir stores tilde path expandable via Path.expanduser()."""
        cfg = Config(log_dir="~/test-logs")
        assert cfg.log_dir == "~/test-logs"
        expanded = Path(cfg.log_dir).expanduser()
        assert expanded == Path.home() / "test-logs"


class TestLLMConfigCustomURLs:
    """LLMConfig — custom base URLs for comms and postmortem."""

    def test_custom_comms_and_postmortem_urls(self) -> None:
        """Custom comms_base_url and postmortem_base_url are stored correctly."""
        cfg = LLMConfig(
            comms_base_url="http://other",
            postmortem_base_url="http://other",
        )
        assert cfg.comms_base_url == "http://other"
        assert cfg.postmortem_base_url == "http://other"
