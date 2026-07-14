# Real-Data Test Plan — Phase B2

> **Goal:** Validate ai-incident-commander against 100 real-world incidents from public datasets, comparing generated postmortems against known ground truth.
>
> **Scope:** 100 incidents from 4 public data sources. Fully local — MLX LLM + in-process sentence-transformers embeddings. $0 API cost. Semantic similarity for RCA accuracy. Automated fixture conversion.
>
> **Owner:** Engineering
> **Status:** Planned

---

## 1. Data Sources

Four public datasets provide the incident corpus. An automated converter transforms each into our fixture format.

| Source | Count Available | Has Raw Telemetry? | Has Ground Truth RCA? | Has Postmortem? | Format |
|--------|----------------|-------------------|----------------------|-----------------|--------|
| **OpenRCA2 v1-500** ([HuggingFace](https://huggingface.co/datasets/lincyaw/openrca2-v1-500)) | 500 | ✅ Logs, metrics, traces (parquet) | ✅ injection.json + causal_graph.json | ❌ | Parquet + JSON |
| **opensre-incident-trajectories** ([HuggingFace](https://huggingface.co/datasets/quantranger/opensre-incident-trajectories)) | 114 real + 83 synthetic | ❌ Reconstructed | ✅ answer field | ✅ source_url to real postmortem | JSON |
| **IntelligentDDS** ([GitHub](https://github.com/IntelligentDDS/Post-mortems-Analysis)) | 354 structured | ❌ Narrative | ✅ Structured fields | ✅ Full text | Markdown |
| **Public blog postmortems** (Cloudflare, AWS, GitHub, etc.) | 20 hand-picked | ❌ Narrative | ✅ From postmortem | ✅ Full text | HTML/Markdown |

**Target:** 100 incidents total, sampled across all 4 sources:
- 50 from OpenRCA2 (raw telemetry — strongest signal)
- 30 from opensre-trajectories (real company postmortems)
- 15 from IntelligentDDS (structured cloud postmortems)
- 5 hand-built from public blog postmortems (Cloudflare, GitLab, GitHub, AWS, Discord)

This gives coverage across 10+ companies and 4+ data source types.

---

## 2. Automated Fixture Converter

A Python script (`scripts/convert_incidents.py`) transforms each dataset into our fixture format.

### OpenRCA2 Converter

Raw dataset: `data/raw/openrca2/` (download from HuggingFace, see README)

```
OpenRCA2 case/
├── injection.json        →  ground_truth.json (root_cause, key_terms)
├── causal_graph.json     →  ground_truth.json (causal chain)
├── abnormal_logs.parquet →  logs.json (LogEntry format)
├── abnormal_metrics.parquet → (metadata for alert.json)
└── env.json              →  meta.json (service, namespace)
```

Output per incident:
```
tests/fixtures/real-data/openrca-<case_name>/
├── meta.json          # incident_id, service, severity, start_time
├── alert.json         # Reconstructed from injection metadata
├── logs.json          # Converted from abnormal_logs.parquet
├── ground_truth.json  # Root cause, causal graph, expected timeline
└── README.md          # Source attribution
```

### opensre-trajectories Converter

Raw dataset: `data/raw/opensre/` (checked into repo, 1.1MB)

```
opensre trajectory JSON
├── scenario_id        →  incident slug
├── source_company     →  meta.json company field
├── source_url         →  README.md link
├── answer             →  ground_truth.json root_cause
├── trap_actions       →  ground_truth.json trap_actions
└── tool transcripts   →  logs.json (simulated from tool calls)
```

### IntelligentDDS Converter

Raw dataset: `data/raw/intelligentdds/` (checked into repo, 276MB)

```
IntelligentDDS structured postmortem
├── summary            →  ground_truth.json root_cause
├── timeline           →  ground_truth.json timeline_events
├── action_items       →  ground_truth.json action_items
└── impact             →  ground_truth.json impact
```

### Blog Postmortem Converter (semi-automated)

Source postmortems: `data/raw/blog/` (hand-curated HTML/markdown files)

For the 5 hand-picked blog postmortems, a helper script extracts the timeline table from the HTML and generates a scaffold. A human reviews and finalizes.

---

## 3. Models — Fully Local

All inference runs locally on Apple Silicon via MLX. **Zero API cost. Zero keys.**

### Analysis LLM (postmortem generation)

- **Primary:** `mlx-community/Qwen3.6-35B-A3B-4bit` — MoE, 3B active, ~20GB RAM
- **Lower RAM:** `mlx-community/Qwen3.5-9B-4bit` — ~6GB RAM
- **Highest quality:** `mlx-community/Qwen3.5-27B-Claude-4.6-Opus-Distilled-MLX-4bit` — ~16GB RAM

### Embedding Model (RCA semantic similarity)

- **Model:** `sentence-transformers/all-MiniLM-L6-v2` — in-process, ~80MB, no server

### Architecture

```
┌──────────────────────────────────────────────┐
│  Mac (Apple Silicon)                          │
│                                               │
│  ┌─────────────┐  ┌────────────────────┐     │
│  │ MLX LLM     │  │ sentence-transform │     │
│  │ Qwen3.6-35B │  │ all-MiniLM-L6-v2   │     │
│  │ (server)    │  │ (in-process)       │     │
│  └──────┬──────┘  └────────┬───────────┘     │
│         └────────┬─────────┘                  │
│                  │                            │
│         ┌────────▼────────┐                   │
│         │ pytest real_data│                   │
│         │ (100 incidents) │                   │
│         └─────────────────┘                   │
└──────────────────────────────────────────────┘
```

One MLX server for LLM. Embeddings run in-process.

---

## 4. Test Criteria (8 Criteria)

| # | Criterion | Measurement | Pass Threshold | Method |
|---|-----------|-------------|----------------|--------|
| 1 | **Root Cause Accuracy** | Cosine similarity between generated RCA embedding and ground truth RCA embedding | ≥0.70 | `sentence-transformers/all-MiniLM-L6-v2` in-process, cosine sim |
| 2 | **Timeline Completeness** | % of ground truth timeline events present in generated timeline | ≥90% | Fuzzy string match at 0.80 similarity threshold |
| 3 | **Action Item Relevance** | % of generated action items matching real action items | ≥50% | Embedding cosine sim per pair, best-match assignment, threshold 0.65 |
| 4 | **Blameless Framing** | Regex matches for blame language in AI sections | 0 hits | Regex: `(engineer\|developer\|blame\|fault of\|negligence\|careless\|mistake by)\b` |
| 5 | **Citation Integrity** | Remediation suggestions with `citation` starting "Source:" | 100% | Check all `RemediationSuggestion` objects |
| 6 | **Cost Predictibility** | Std-dev / mean of total cost across 3 runs | ≤0.20 | Run same incident 3×, compute coefficient of variation |
| 7 | **Graceful Degradation** | Incomplete input (missing logs or messages) | Exit code 0, warnings, no crash | Feed partial data, check exit code + stderr |
| 8 | **No Hallucination** | Generated events not traceable to input data | 0 fabricated items | **Heuristic:** for each generated timeline event, check if at least one keyword from the event appears in the input logs/messages/alert. Events with zero keyword overlap are flagged as potential hallucinations |

---

## 5. Fixture Format

```
tests/fixtures/real-data/
├── openrca-train-ticket-db-pool-exhaustion/
│   ├── README.md           # Source: OpenRCA2, case name, HuggingFace URL
│   ├── meta.json           # incident_id, service, severity, start_time
│   ├── alert.json          # Reconstructed alert
│   ├── logs.json           # Converted from parquet
│   ├── ground_truth.json   # Known RCA, timeline, action items
│   └── source_type         # "openrca2" | "opensre" | "intelligentdds" | "blog"
├── opensre-slack-tgw-fd-exhaustion/
│   └── ...
├── intelligentdds-aws-s3-2017/
│   └── ...
└── blog-cloudflare-dns-2025/
    └── ...
```

### ground_truth.json Schema

```json
{
  "schema_version": "1.0",
  "incident_id": "openrca-train-ticket-db-pool-exhaustion",
  "source_type": "openrca2",
  "source_url": "https://huggingface.co/datasets/lincyaw/openrca2-v1-500",
  "company": "OpenRCA2 (train-ticket)",
  "root_cause": "Database connection pool exhaustion due to connection leak in cart service",
  "root_cause_key_terms": ["connection pool", "exhaustion", "leak", "cart service"],
  "timeline_events": [
    {"time": "2026-01-15T14:00:00Z", "event": "Connection pool reached max capacity"},
    {"time": "2026-01-15T14:05:00Z", "event": "Cart service started timing out"}
  ],
  "action_items": [
    "Fix connection leak in cart service checkout flow",
    "Add connection pool monitoring alerting at 80% utilization"
  ],
  "impact": "Cart service unavailable for 15 minutes",
  "severity": "SEV1",
  "service": "cart-service"
}
```

---

## 6. Test Code Structure

```python
# tests/real_data/conftest.py
"""Shared fixtures and helpers for real-data tests."""

import json
import pytest
from pathlib import Path
from sentence_transformers import SentenceTransformer, util

FIXTURE_DIR = Path("tests/fixtures/real-data")

# Load embedding model once (in-process, no server needed)
_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def load_incident_fixture(slug: str) -> dict:
    """Load all fixture files for an incident."""
    d = FIXTURE_DIR / slug
    return {
        "meta": json.loads((d / "meta.json").read_text()),
        "alert": json.loads((d / "alert.json").read_text()),
        "logs": json.loads((d / "logs.json").read_text()) if (d / "logs.json").exists() else [],
        "ground_truth": json.loads((d / "ground_truth.json").read_text()),
    }


def embed(text: str) -> list[float]:
    """Get embedding from in-process sentence-transformers model."""
    return get_embedding_model().encode(text).tolist()


def cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    import math
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
```

```python
# tests/real_data/test_real_incidents.py
"""Real-data tests: feed real incident data through tool, compare with ground truth."""

import re
import pytest
from incident_commander.api import run_incident
from tests.real_data.conftest import load_incident_fixture, embed, cosine_sim

FIXTURE_DIR = Path("tests/fixtures/real-data")
REAL_INCIDENTS = [d.name for d in FIXTURE_DIR.iterdir() if d.is_dir()]

BLAME_REGEX = re.compile(r"\b(engineer|developer|blame|fault of|negligence|careless|mistake by)\b", re.I)


@pytest.mark.real_data
@pytest.mark.parametrize("incident_slug", REAL_INCIDENTS)
class TestRealIncidents:

    def test_root_cause_accuracy(self, incident_slug):
        fixture = load_incident_fixture(incident_slug)
        result = run_incident(
            alert=fixture["alert"],
            logs=fixture["logs"],
            auto_approve=True,
        )
        rca_emb = embed(result.postmortem.rca.content)
        truth_emb = embed(fixture["ground_truth"]["root_cause"])
        assert cosine_sim(rca_emb, truth_emb) >= 0.70

    def test_timeline_completeness(self, incident_slug): ...
    def test_action_item_relevance(self, incident_slug): ...
    def test_blameless_framing(self, incident_slug):
        fixture = load_incident_fixture(incident_slug)
        result = run_incident(alert=fixture["alert"], logs=fixture["logs"], auto_approve=True)
        ai_sections = [s.content for s in result.postmortem.sections if s.ai_generated]
        for section in ai_sections:
            assert not BLAME_REGEX.search(section)

    def test_citation_integrity(self, incident_slug): ...
    def test_cost_predictability(self, incident_slug): ...
    def test_graceful_degradation(self, incident_slug): ...
    def test_no_hallucination(self, incident_slug): ...
```

---

## 7. Results Document

After running, results are written to `docs/field-test-results.md`:

```markdown
# Field Test Results

> Generated: YYYY-MM-DD
> LLM: mlx-community/Qwen3.6-35B-A3B-4bit (local, MLX)
> Embeddings: sentence-transformers/all-MiniLM-L6-v2 (in-process)
> Cost: $0.00 (fully local)

| Incident | Source | RCA Sim | Timeline | Actions | Blameless | Citation | Cost CV | Degrade | No Hall | Overall |
|---|---|---|---|---|---|---|---|---|---|---|
| openrca-db-pool | openrca2 | 0.82 ✅ | 5/5 ✅ | 3/4 ✅ | 0 ✅ | 100% ✅ | 0.12 ✅ | ✅ | ✅ | 8/8 |
| opensre-slack-tgw | opensre | 0.65 ❌ | 4/5 ✅ | 2/4 ✅ | 0 ✅ | 100% ✅ | 0.18 ✅ | ✅ | ❌ | 6/8 |

**Overall pass rate:** X/800 checks (X%)
**By source:** OpenRCA2 X%, opensre X%, IntelligentDDS X%, blog X%
**Known limitations:** ...
**Recommendations for v0.2.0:** ...
```

---

## 8. How to Run

### Prerequisites

```bash
# mlx-lm, sentence-transformers, transformers already installed
# Install pyarrow for parquet reading (OpenRCA2 datasets)
pip install pyarrow

# Models are already downloaded in ~/.cache/huggingface/hub/
# all-MiniLM-L6-v2 auto-downloads on first run (~80MB)
```

### Start local LLM server

```bash
# Only ONE server needed — MLX LLM for postmortem generation
mlx_lm.server --model mlx-community/Qwen3.6-35B-A3B-4bit --port 8080
```

### Configure and run

```bash
# Point tool at local MLX LLM
export LLM_MODEL=qwen3.6-35b-a3b
export LLM_BASE_URL=http://localhost:8080/v1

# Convert datasets to fixtures (one-time)
python scripts/convert_incidents.py --source openrca2 --count 50
python scripts/convert_incidents.py --source opensre --count 30
python scripts/convert_incidents.py --source intelligentdds --count 15
python scripts/convert_incidents.py --source blog --count 5

# Run all real-data tests (takes ~2-3 hours for 100 incidents on MLX)
pytest tests/real_data/ -m real_data -v

# Run a single incident
pytest tests/real_data/ -m real_data -k "openrca-db-pool"

# Run only OpenRCA2 incidents
pytest tests/real_data/ -m real_data -k "openrca"

# Generate results report
python scripts/generate_field_test_report.py --output docs/field-test-results.md
```

### Lower-RAM alternative

If 35B is too heavy, use the 9B model:

```bash
mlx_lm.server --model mlx-community/Qwen3.5-9B-4bit --port 8080
export LLM_MODEL=qwen3.5-9b
```

---

## 9. Cost Estimate

| Component | Cost |
|-----------|------|
| LLM inference (local MLX) | $0.00 |
| Embedding inference (in-process sentence-transformers) | $0.00 |
| HuggingFace dataset download | $0.00 |
| **Total** | **$0.00** |

---

## 10. Implementation Plan

| Step | Task | Effort |
|------|------|--------|
| 1 | Write `scripts/convert_incidents.py` — OpenRCA2 converter (parquet → JSON) | 4h |
| 2 | Add opensre-trajectories converter | 2h |
| 3 | Add IntelligentDDS converter | 2h |
| 4 | Hand-build 5 blog postmortem fixtures | 3h |
| 5 | Write `tests/real_data/conftest.py` — fixture loader, MLX embedding helper | 2h |
| 6 | Write `tests/real_data/test_real_incidents.py` — 8 criteria tests | 4h |
| 7 | Write `scripts/generate_field_test_report.py` | 2h |
| 8 | Start MLX servers, run tests, generate results | 3h |
| 9 | Add `pyarrow` to dev deps (mlx-lm already installed) | 0.5h |
| **Total** | | **~22h** |

---

## 11. Available MLX Models

Already downloaded on this machine (`~/.cache/huggingface/hub/`):

### LLMs (for postmortem generation)

| Model | Active Params | RAM | Use Case |
|-------|--------------|-----|----------|
| **Qwen3.6-35B-A3B-4bit** | 3B (MoE) | ~20GB | **Recommended** — best quality/speed ratio |
| Qwen3.5-27B-Claude-4.6-Opus-Distilled-MLX-4bit | 27B | ~16GB | Highest prose quality (Claude-distilled) |
| Qwen3.6-27B-4bit | 27B | ~16GB | Strong reasoning |
| Qwen3.5-9B-4bit | 9B | ~6GB | Lower RAM, good quality |
| Qwen3-8B-4bit | 8B | ~6GB | Solid all-rounder |

### Embedding Model (for RCA similarity)

| Model | RAM | Use Case |
|-------|-----|----------|
| **Qwen3-Embedding-4B-4bit-DWQ** | ~3GB | **Recommended** — native Qwen embeddings |

### Coder Models (not recommended for postmortem prose)

| Model | RAM | Notes |
|-------|-----|-------|
| Qwen3-Coder-30B-A3B-Instruct-4bit | ~18GB | Code-focused, weaker prose |
| Qwen2.5-Coder-14B-Instruct-4bit | ~10GB | Current default, code-focused |
| Qwen2.5.1-Coder-7B-Instruct-4bit | ~5GB | Current default, code-focused |
