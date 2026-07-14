"""Tests for the rag module: InMemoryRetriever, retrieve_runbooks_node."""

from __future__ import annotations

from incident_commander.models.input import Runbook
from incident_commander.models.state import Alert, IncidentState
from incident_commander.nodes.rag import (
    InMemoryRetriever,
    _build_result,
    _keyword_overlap,
    _service_match,
    init_retriever,
    retrieve_runbooks_node,
)


class TestInMemoryRetriever:
    """InMemoryRetriever — keyword-based runbook and incident retrieval."""

    def _build_retriever(self) -> InMemoryRetriever:
        # Three runbooks: service-specific (payment, gateway), and wildcard (*)
        # Wildcard runbooks must match any service query
        r = InMemoryRetriever()
        r.index([
            Runbook(
                id="rb-001", title="DB Pool Exhaustion",
                content="Steps for DB pool",
                keywords=["db", "connection", "pool"],
                service="payment-service",
            ),
            Runbook(
                id="rb-002", title="Rollback Procedure",
                content="How to rollback",
                keywords=["rollback", "deploy"],
                service="*",
            ),
            Runbook(
                id="rb-003", title="Cert Renewal",
                content="Renew TLS cert",
                keywords=["tls", "cert"],
                service="api-gateway",
            ),
        ])
        return r

    def test_query_by_service(self) -> None:
        """Query by service name returns runbooks for that service."""
        r = self._build_retriever()
        results = r.query_runbooks("payment-service", "db connection")
        assert len(results) > 0
        # Results must include both service-specific and wildcard (*) runbooks
        assert all(res["service"] in ("payment-service", "*") for res in results)

    def test_query_by_keyword(self) -> None:
        """Query by symptoms returns runbooks with matching keywords."""
        r = self._build_retriever()
        results = r.query_runbooks("payment-service", "connection pool exhausted")
        assert len(results) > 0
        assert any("pool" in str(res["keywords"]) for res in results)

    def test_results_have_citation(self) -> None:
        """Results include a citation string."""
        # Citation is required for every returned runbook (used in LLM prompts)
        r = self._build_retriever()
        results = r.query_runbooks("payment-service", "db pool")
        assert all(res["citation"] for res in results)

    def test_results_have_relevance_score(self) -> None:
        """Results include a relevance_score."""
        r = self._build_retriever()
        results = r.query_runbooks("payment-service", "db pool")
        assert all(isinstance(res["relevance_score"], float) for res in results)

    def test_empty_index_returns_empty(self) -> None:
        """Empty retriever index returns empty list."""
        r = InMemoryRetriever()
        assert r.query_runbooks("any", "test") == []

    def test_no_match_returns_empty(self) -> None:
        """No matching runbooks returns empty list."""
        # Both service mismatch AND keyword mismatch — must return [] not crash
        r = InMemoryRetriever()
        r.index([
            Runbook(
                id="rb-001", title="DB Pool", content="Steps",
                keywords=["db"], service="payment-service",
            ),
        ])
        results = r.query_runbooks("unknown-service", "zzz_nonexistent")
        assert results == []


class TestRetrieveRunbooksNode:
    """retrieve_runbooks_node — LangGraph node."""

    def test_stores_results_in_state(self) -> None:
        """Node stores results in state.retrieved_runbooks."""
        # init_retriever sets a global singleton used by the LangGraph node
        r = InMemoryRetriever()
        r.index([
            Runbook(
                id="rb-001", title="DB Pool",
                content="steps", keywords=["db"], service="srv",
            ),
        ])
        init_retriever(r)
        state = IncidentState()
        state.service = "srv"
        state.alert = Alert(
            severity="SEV1", service="srv",
            summary="db pool exhausted",
            timestamp="2026-07-13T14:00:00",  # type: ignore[arg-type]
        )
        result = retrieve_runbooks_node(state)
        assert len(result.retrieved_runbooks) > 0

    def test_retrieved_incidents_in_state(self) -> None:
        """Node stores past incidents in state.retrieved_incidents."""
        # retrieved_incidents is populated even with empty retriever (always a list)
        r = InMemoryRetriever()
        init_retriever(r)
        state = IncidentState()
        state.service = "srv"
        from datetime import datetime
        state.alert = Alert(
            severity="SEV2", service="srv",
            summary="test", timestamp=datetime.now(),
        )
        result = retrieve_runbooks_node(state)
        assert isinstance(result.retrieved_incidents, list)


class TestKeywordOverlap:
    """_keyword_overlap — count query tokens found in keyword list."""

    def test_hyphen_normalization(self) -> None:
        """Keywords with hyphens match space-separated query tokens."""
        result = _keyword_overlap({"high", "cpu"}, ["high-cpu"])
        assert result > 0

    def test_db_connection(self) -> None:
        """Compound keyword matches multiple query tokens."""
        result = _keyword_overlap({"database", "connection"}, ["db-connection-pool"])
        assert result >= 1


class TestServiceMatch:
    """_service_match — exact or wildcard service comparison."""

    def test_wildcard(self) -> None:
        """Wildcard '*' matches any service."""
        assert _service_match("any-service", "*") is True

    def test_same_service(self) -> None:
        """Exact match returns True."""
        assert _service_match("payment", "payment") is True

    def test_different_service(self) -> None:
        """Different services return False."""
        assert _service_match("payment", "api-gateway") is False


class TestBuildResult:
    """_build_result — constructs standard result dict from entry."""

    def test_with_runbook_object(self) -> None:
        """Runbook object produces correct result dict."""
        rb = Runbook(
            id="rb-001", title="DB Pool", content="steps",
            keywords=["db"], service="payment", path="/runbooks/db.md",
        )
        result = _build_result(rb, 2.5, "snippet", "runbook")
        assert result["title"] == "DB Pool"
        assert result["path"] == "/runbooks/db.md"
        assert result["content_snippet"] == "snippet"
        assert result["keywords"] == ["db"]
        assert result["service"] == "payment"
        assert result["citation"] == "DB Pool (/runbooks/db.md)"
        assert result["relevance_score"] == 2.5
        assert result["type"] == "runbook"

    def test_with_dict(self) -> None:
        """Dict entry produces correct result dict."""
        entry: dict[str, object] = {
            "summary": "Past Incident 123",
            "keywords": ["timeout"],
            "service": "api-gateway",
            "id": "INC-2023-001",
        }
        result = _build_result(entry, 1.0, "snippet text", "past_incident")
        assert result["title"] == "Past Incident 123"
        assert result["path"] == ""
        assert result["content_snippet"] == "snippet text"
        assert result["keywords"] == ["timeout"]
        assert result["service"] == "api-gateway"
        assert result["citation"] == "INC-2023-001"
        assert result["relevance_score"] == 1.0
        assert result["type"] == "past_incident"


class _ErrorRetriever:
    """Mock Retriever that always raises RuntimeError."""

    def index(self, runbooks: list[Runbook]) -> None:
        pass

    def index_past_incidents(self, incidents: list[dict]) -> None:
        pass

    def query_runbooks(self, service: str, symptoms: str) -> list[dict]:
        raise RuntimeError("query_runbooks failed")

    def query_past_incidents(self, service: str, symptoms: str) -> list[dict]:
        raise RuntimeError("query_past_incidents failed")


class TestRetrieverErrors:
    """retrieve_runbooks_node — error handling."""

    def test_retriever_error_runbooks(self) -> None:
        """RuntimeError in query_runbooks does not propagate; returns []."""
        init_retriever(_ErrorRetriever())
        state = IncidentState()
        state.service = "srv"
        state.alert = Alert(
            severity="SEV1", service="srv",
            summary="test error",
            timestamp="2026-07-13T14:00:00",  # type: ignore[arg-type]
        )
        result = retrieve_runbooks_node(state)
        assert result.retrieved_runbooks == []

    def test_retriever_error_past_incidents(self) -> None:
        """RuntimeError in query_past_incidents does not propagate; returns []."""
        init_retriever(_ErrorRetriever())
        state = IncidentState()
        state.service = "srv"
        state.alert = Alert(
            severity="SEV1", service="srv",
            summary="test error",
            timestamp="2026-07-13T14:00:00",  # type: ignore[arg-type]
        )
        result = retrieve_runbooks_node(state)
        assert result.retrieved_incidents == []
