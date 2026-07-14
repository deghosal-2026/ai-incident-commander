"""Shared fixtures and helpers for real-data field tests."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import pytest
from sentence_transformers import SentenceTransformer, util

from incident_commander.config import Config, LLMConfig

FIXTURE_DIR = Path("tests/fixtures/real-data")

ALL_INCIDENTS = sorted(
    d.name for d in FIXTURE_DIR.iterdir()
    if d.is_dir() and not d.name.startswith(".")
)

BLAME_RE = re.compile(
    r"\b(engineer|developer|blame|fault of|negligence|careless|mistake by)\b",
    re.I,
)

# Config from env vars (set before running tests)
MLX_CONFIG = Config(
    llm=LLMConfig(
        analysis_model=os.environ.get("LLM_MODEL", "Qwen3.5-4B-4bit"),
        analysis_base_url=os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1"),
    ),
)

_embedding_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def load_fixture(slug: str) -> dict:
    d = FIXTURE_DIR / slug
    return {
        "meta": json.loads((d / "meta.json").read_text()),
        "alert": json.loads((d / "alert.json").read_text()),
        "logs": json.loads((d / "logs.json").read_text()) if (d / "logs.json").exists() else [],
        "ground_truth": json.loads((d / "ground_truth.json").read_text()),
    }


def embed(text: str) -> list[float]:
    return _get_model().encode(text).tolist()


def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def fuzzy_match(a: str, b: str, threshold: float = 0.8) -> bool:
    emb_a = embed(a)
    emb_b = embed(b)
    return cosine_sim(emb_a, emb_b) >= threshold
