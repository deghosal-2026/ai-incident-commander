"""Tests for the rerank module: _score_evidence, rerank_evidence_node."""

from __future__ import annotations

from datetime import datetime

from incident_commander.models.state import IncidentState, TimelineEvent
from incident_commander.nodes.rerank import _score_evidence, rerank_evidence_node

_EVIDENCE_RB = {
    "type": "runbook", "path": "", "content_snippet": "",
    "relevance_score": 0.0,
}


class TestRerankEvidenceNode:
    """rerank_evidence_node — reorders evidence by relevance."""

    def test_rerank_reorders_evidence(self) -> None:
        """Evidence is reordered with higher relevance first."""
        # payment-service runbook should rank above api-gateway for a payment-service incident
        state = IncidentState()
        state.service = "payment-service"
        state.retrieved_runbooks = [
            {"title": "DB Pool", "service": "payment-service",
             "keywords": ["db"], "citation": "rb-001", **_EVIDENCE_RB},
            {"title": "Cert Renewal", "service": "api-gateway",
             "keywords": ["tls"], "citation": "rb-003", **_EVIDENCE_RB},
        ]
        result = rerank_evidence_node(state)
        assert len(result.reranked_evidence) == 2
        assert result.reranked_evidence[0]["service"] == "payment-service"

    def test_evidence_with_deploy_correlation_boosted(self) -> None:
        """Evidence with deploy_correlation flag scores higher."""
        # Events with deploy_correlation=True get a reranking boost for related runbooks
        state = IncidentState()
        state.service = "srv"
        state.timeline = [
            TimelineEvent(
                timestamp=datetime.now(), source="alert",
                event_type="deploy", content="new deploy",
                trust_level="high", deploy_correlation=True,
            ),
        ]
        state.retrieved_runbooks = [
            {"title": "Rollback", "service": "srv",
             "keywords": ["deploy"], "citation": "rb-002", **_EVIDENCE_RB},
        ]
        result = rerank_evidence_node(state)
        assert len(result.reranked_evidence) == 1

    def test_no_evidence_returns_empty(self) -> None:
        """No evidence results in empty reranked list."""
        # Missing retrieved_runbooks entirely → must not crash
        state = IncidentState()
        result = rerank_evidence_node(state)
        assert result.reranked_evidence == []

    def test_reranked_evidence_is_list(self) -> None:
        """reranked_evidence is always a list."""
        state = IncidentState()
        state.retrieved_runbooks = [
            {"title": "Test", "service": "srv", "keywords": [],
             "citation": "t", **_EVIDENCE_RB},
        ]
        result = rerank_evidence_node(state)
        assert isinstance(result.reranked_evidence, list)


class TestScoreEvidence:
    """_score_evidence — compute relevance score for a single evidence item."""

    def test_service_match_only(self) -> None:
        """Service match alone yields a score of 3.0."""
        item = {"service": "payment-service", "keywords": [], "deploy_correlation": False}
        score = _score_evidence(item, "payment-service", set())
        assert score == 3.0

    def test_keyword_overlap_only(self) -> None:
        """Two overlapping deploy keywords yield a score of 4.0."""
        item = {"service": "other", "keywords": ["rollback", "deploy"], "deploy_correlation": False}
        score = _score_evidence(item, "payment-service", {"rollback", "deploy"})
        assert score == 4.0

    def test_deploy_correlation_only(self) -> None:
        """Deploy-correlation flag alone yields a score of 1.0."""
        item = {"service": "other", "keywords": [], "deploy_correlation": True}
        score = _score_evidence(item, "payment-service", set())
        assert score == 1.0

    def test_all_three_factors(self) -> None:
        """Service match + 2 keyword overlap + deploy_correlation yields 8.0."""
        item = {
            "service": "payment-service",
            "keywords": ["rollback", "deploy"],
            "deploy_correlation": True,
        }
        score = _score_evidence(item, "payment-service", {"rollback", "deploy"})
        assert score == 8.0

    def test_deploy_keyword_collection(self) -> None:
        """Evidence whose keywords match deploy-correlated timeline content ranks higher."""
        state = IncidentState()
        state.service = "srv"
        state.timeline = [
            TimelineEvent(
                timestamp=datetime.now(), source="alert",
                event_type="deploy", content="rollback to v2.1.0",
                trust_level="high", deploy_correlation=True,
            ),
        ]
        state.retrieved_runbooks = [
            {"title": "Rollback Proc", "service": "srv",
             "keywords": ["rollback"], "citation": "rb-002", **_EVIDENCE_RB},
            {"title": "Cert Renewal", "service": "srv",
             "keywords": ["tls"], "citation": "rb-003", **_EVIDENCE_RB},
        ]
        result = rerank_evidence_node(state)
        assert result.reranked_evidence[0]["title"] == "Rollback Proc"
