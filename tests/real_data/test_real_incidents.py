"""Real-data field tests: 8 criteria across all incidents.

Run with:
  export LLM_MODEL=deepseek-v4-flash
  export LLM_BASE_URL=https://opencode.ai/zen/v1
  export LLM_API_KEY=<your-key>
  pytest tests/real_data/ -m real_data -v
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from incident_commander.api import run_incident
from tests.real_data import (
    ALL_INCIDENTS,
    BLAME_RE,
    FIXTURE_DIR,
    MLX_CONFIG,
    cosine_sim,
    embed,
    fuzzy_match,
    load_fixture,
)


def _ai_sections(postmortem) -> list[str]:
    """Collect content from all AI-generated postmortem sections."""
    contents = []
    for field in ["summary", "root_cause_analysis", "systemic_contributing_factors",
                   "customer_impact", "regulatory_compliance_impact",
                   "stakeholder_communication_log"]:
        section = getattr(postmortem, field, None)
        if section is not None and getattr(section, "ai_generated", True):
            contents.append(section.content)
    return contents


def _run(incident_slug: str, with_logs: bool = True):
    """Run incident through the tool, save generated output, return result."""
    f = load_fixture(incident_slug)
    out_dir = str(FIXTURE_DIR / incident_slug / "generated")
    config = MLX_CONFIG.model_copy()
    config.log_dir = out_dir
    return run_incident(
        alert=f["alert"],
        logs=f["logs"] if with_logs else None,
        config=config,
        output_dir=out_dir,
        auto_approve=True,
    )


@pytest.mark.real_data
@pytest.mark.parametrize("incident_slug", ALL_INCIDENTS)
class TestRealIncidents:

    def test_root_cause_accuracy(self, incident_slug):
        """Generated RCA embedding matches ground truth (cos sim >= 0.70)."""
        f = load_fixture(incident_slug)
        result = _run(incident_slug)
        rca_emb = embed(result.postmortem.root_cause_analysis.content)
        truth_emb = embed(f["ground_truth"]["root_cause"])
        sim = cosine_sim(rca_emb, truth_emb)
        assert sim >= 0.70, f"RCA similarity {sim:.3f} < 0.70"

    def test_timeline_completeness(self, incident_slug):
        """>= 80% of ground truth timeline events present in generated timeline."""
        f = load_fixture(incident_slug)
        result = _run(incident_slug)
        gt_events = f["ground_truth"].get("timeline_events", [])
        if not gt_events:
            pytest.skip("No ground truth timeline events")
        gen_timeline = [e.content for e in result.timeline]
        matched = sum(
            1 for gt in gt_events
            if any(fuzzy_match(gt["event"], gen) for gen in gen_timeline)
        )
        ratio = matched / len(gt_events)
        assert ratio >= 0.80, f"Timeline coverage {ratio:.2f} ({matched}/{len(gt_events)})"

    def test_action_item_relevance(self, incident_slug):
        """>= 50% of generated action items match ground truth."""
        f = load_fixture(incident_slug)
        result = _run(incident_slug)
        gt_actions = f["ground_truth"].get("action_items", [])
        if not gt_actions:
            pytest.skip("No ground truth action items")
        gen_actions = [a.description for a in result.postmortem.action_items]
        matched = sum(
            1 for gen in gen_actions
            if any(fuzzy_match(gen, gt) for gt in gt_actions)
        )
        ratio = matched / len(gen_actions) if gen_actions else 0
        assert ratio >= 0.50, f"Action item match {ratio:.2f} ({matched}/{len(gen_actions)})"

    def test_blameless_framing(self, incident_slug):
        """Zero blame language in AI-generated sections."""
        result = _run(incident_slug)
        sections = _ai_sections(result.postmortem)
        hits = sum(len(BLAME_RE.findall(s)) for s in sections)
        assert hits == 0, f"Found {hits} blame instances"

    def test_citation_integrity(self, incident_slug):
        """Every remediation suggestion has citation starting with 'Source:'."""
        result = _run(incident_slug)
        for s in result.remediation_suggestions:
            assert s.citation and s.citation.startswith("Source:"), (
                f"Missing citation: {s.action[:50]}"
            )

    def test_cost_predictability(self, incident_slug):
        """Cost CV <= 0.20 across 3 runs."""
        costs = []
        for _ in range(3):
            result = _run(incident_slug)
            costs.append(result.cost_report.total_estimated_cost_usd)
        mean = float(np.mean(costs))
        if mean == 0:
            pytest.skip("Zero cost")
        cv = float(np.std(costs)) / mean
        assert cv <= 0.20, f"Cost CV {cv:.3f} > 0.20"

    def test_graceful_degradation(self, incident_slug):
        """Incomplete input (no logs) produces valid output, no crash."""
        result = _run(incident_slug, with_logs=False)
        assert result is not None
        assert result.thread_id != ""

    def test_no_hallucination(self, incident_slug):
        """Each generated timeline event has >=1 keyword match in input."""
        f = load_fixture(incident_slug)
        result = _run(incident_slug)
        input_text = json.dumps(f["alert"]).lower() + " " + " ".join(
            e["message"] for e in f["logs"][:100]
        ).lower()
        input_keywords = set(input_text.split())
        hallucinated = 0
        for event in result.timeline:
            event_words = set(event.content.lower().split())
            if not (event_words & input_keywords):
                hallucinated += 1
        assert hallucinated == 0, f"Found {hallucinated} events with no keyword overlap"
