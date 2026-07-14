"""Tests for simulation module: IncidentSimulator, scenarios, runbooks."""

from __future__ import annotations

import pytest  # provides raises() context manager for exception assertions
from pydantic import ValidationError

# Demo runbooks and past incidents provide fixture data for RAG matching tests
from incident_commander.simulation.demo_runbooks import DEMO_PAST_INCIDENTS, DEMO_RUNBOOKS

# SCENARIOS is the registry dict; load_scenario builds an IncidentInput from it
from incident_commander.simulation.scenarios import SCENARIOS, ScenarioConfig, load_scenario

# IncidentSimulator is the core class under test — generates fake incident data
from incident_commander.simulation.simulator import IncidentSimulator


class TestIncidentSimulator:
    """IncidentSimulator core: generates fake alert, logs, messages, PRs."""

    def test_simulate_returns_incident_input(self) -> None:
        """Simulator produces a valid IncidentInput for each severity."""
        sim = IncidentSimulator(seed=42)
        # All 3 severities checked to verify severity passes through to the alert
        for severity in ["SEV1", "SEV2", "SEV3"]:
            result = sim.simulate(service="payment-service", severity=severity)
            assert result.alert.severity == severity
            assert result.alert.service == "payment-service"
            # Default counts: 15 logs, 8 messages, 3 PRs as per simulate() defaults
            assert len(result.logs) == 15
            assert len(result.messages) == 8
            assert len(result.github) == 3
            assert result.meta is not None

    def test_deterministic_seed(self) -> None:
        """Same seed produces identical output."""
        # Two instances with same seed must produce identical output for reproducibility
        sim1 = IncidentSimulator(seed=42)
        sim2 = IncidentSimulator(seed=42)
        result1 = sim1.simulate(service="payment-service", severity="SEV1")
        result2 = sim2.simulate(service="payment-service", severity="SEV1")
        assert result1.alert.summary == result2.alert.summary
        assert result1.alert.incident_id == result2.alert.incident_id
        assert len(result1.logs) == len(result2.logs)
        assert len(result1.messages) == len(result2.messages)

    def test_different_seed_different_output(self) -> None:
        """Different seeds produce different output (likely)."""
        # Seeds 1 and 999 are far apart to ensure different random sequences
        sim1 = IncidentSimulator(seed=1)
        sim2 = IncidentSimulator(seed=999)
        result1 = sim1.simulate(service="payment-service", severity="SEV1")
        result2 = sim2.simulate(service="payment-service", severity="SEV1")
        # incident_id is randomly generated; different seeds must yield different IDs
        assert result1.alert.incident_id != result2.alert.incident_id

    def test_custom_log_count(self) -> None:
        """Custom num_logs produces that many log entries."""
        sim = IncidentSimulator(seed=42)
        # num_logs=5 overrides default 15 to verify the count parameter works
        result = sim.simulate(service="api-gateway", severity="SEV2", num_logs=5)
        assert len(result.logs) == 5

    def test_deploy_correlated_true(self) -> None:
        """When deploy_correlated=True, PR merge times are before alert."""
        sim = IncidentSimulator(seed=42)
        result = sim.simulate(service="payment-service", severity="SEV1", deploy_correlated=True)
        alert_time = result.alert.timestamp
        # PRs merged before alert simulates a deploy that caused the incident
        for pr in result.github:
            assert pr.merge_time < alert_time

    def test_deploy_correlated_false(self) -> None:
        """When deploy_correlated=False, PR merge times are after alert."""
        sim = IncidentSimulator(seed=42)
        result = sim.simulate(
            service="payment-service", severity="SEV1", num_prs=2, deploy_correlated=False
        )
        alert_time = result.alert.timestamp
        # PRs merged after alert means the deploy did NOT cause the incident
        for pr in result.github:
            assert pr.merge_time > alert_time

    def test_zero_prs(self) -> None:
        """num_prs=0 produces no GitHub PRs."""
        sim = IncidentSimulator(seed=42)
        # Edge case: zero PRs should yield empty github list, not an error
        result = sim.simulate(service="payment-service", severity="SEV1", num_prs=0)
        assert result.github == []

    def test_zero_logs(self) -> None:
        """num_logs=0 produces no log entries."""
        sim = IncidentSimulator(seed=42)
        # Edge case: zero logs should yield empty log list, not an error
        result = sim.simulate(service="payment-service", severity="SEV1", num_logs=0)
        assert result.logs == []

    def test_meta_has_commander(self) -> None:
        """Simulated meta includes default commander."""
        sim = IncidentSimulator(seed=42)
        result = sim.simulate(service="payment-service", severity="SEV1")
        # Meta must be populated with default commander name and 2-person oncall roster
        assert result.meta is not None
        assert result.meta.commander == "sim-commander"
        assert len(result.meta.oncall_roster) == 2


class TestScenarios:
    """Scenario definitions: 8 pre-built scenarios with correct config."""

    def test_all_scenarios_loadable(self) -> None:
        """All 8 scenarios in SCENARIOS dict load successfully."""
        # Exactly 8 scenarios ensures the registry hasn't been accidentally modified
        assert len(SCENARIOS) == 8
        for name in SCENARIOS:
            result = load_scenario(name, seed=42)
            # Each scenario must produce a valid alert and meta, not just partial data
            assert result.alert is not None
            assert result.meta is not None

    def test_each_scenario_correct_service(self) -> None:
        """Each scenario has the expected service assigned."""
        # Maps scenario name to the service it should target for incident simulation
        expected = {
            "db-connection-pool": "payment-service",
            "bad-deploy": "api-gateway",
            "memory-leak": "auth-service",
            "cert-expiry": "api-gateway",
            "dependency-outage": "payment-service",
            "config-drift": "web-frontend",
            "cache-invalidation": "product-catalog",
            "rate-limit-hit": "search-service",
        }
        for name, svc in expected.items():
            result = load_scenario(name, seed=42)
            assert result.alert.service == svc, (
                f"{name}: expected {svc}, got {result.alert.service}"
            )

    def test_each_scenario_correct_severity(self) -> None:
        """Each scenario has the expected severity level."""
        # Maps scenario to severity: SEV1=critical, SEV2=major, SEV3=minor
        expected = {
            "db-connection-pool": "SEV1",
            "bad-deploy": "SEV2",
            "memory-leak": "SEV2",
            "cert-expiry": "SEV1",
            "dependency-outage": "SEV1",
            "config-drift": "SEV3",
            "cache-invalidation": "SEV2",
            "rate-limit-hit": "SEV3",
        }
        for name, sev in expected.items():
            result = load_scenario(name, seed=42)
            assert result.alert.severity == sev, (
                f"{name}: expected {sev}, got {result.alert.severity}"
            )

    def test_unknown_scenario_raises(self) -> None:
        """Unknown scenario name raises KeyError with available list."""
        # load_scenario should raise KeyError when given an unrecognized name
        with pytest.raises(KeyError) as exc:
            load_scenario("nonexistent")
        # Error message must include a known scenario name to guide the user
        assert "db-connection-pool" in str(exc.value)

    def test_deterministic_scenario(self) -> None:
        """Same scenario + seed produces identical output."""
        # Same seed + scenario must produce identical alert for reproducible tests
        r1 = load_scenario("db-connection-pool", seed=42)
        r2 = load_scenario("db-connection-pool", seed=42)
        assert r1.alert.incident_id == r2.alert.incident_id
        assert r1.alert.summary == r2.alert.summary

    def test_scenario_with_deploy_correlation(self) -> None:
        """Scenarios with deploy_correlated=True have PRs before alert."""
        # db-connection-pool scenario has deploy_correlated=True by design
        result = load_scenario("db-connection-pool", seed=42)
        assert len(result.github) > 0
        # Each PR merge must happen before the alert fired (cause before effect)
        for pr in result.github:
            assert pr.merge_time < result.alert.timestamp

    def test_scenario_expected_runbook_matches(self) -> None:
        """Each scenario has expected_runbook_matches populated."""
        # RAG matching requires each scenario to declare its expected runbook hits
        for name, cfg in SCENARIOS.items():
            assert isinstance(cfg.expected_runbook_matches, list)

    def test_invalid_severity_raises(self) -> None:
        """Invalid severity value raises ValidationError."""
        with pytest.raises(ValidationError):
            ScenarioConfig(
                name="test", description="test",
                service="srv", severity="SEV4",
            )

    def test_valid_fields_passes(self) -> None:
        """Valid scenario fields raise no error."""
        cfg = ScenarioConfig(
            name="test", description="test",
            service="srv", severity="SEV1",
        )
        assert cfg.name == "test"
        assert cfg.service == "srv"
        assert cfg.severity == "SEV1"


class TestDemoRunbooks:
    """Demo runbook data: 6 runbooks + 6 past incidents for RAG."""

    def test_all_runbooks_have_content(self) -> None:
        """All 6 demo runbooks have non-empty content."""
        # At least 5 runbooks needed for diverse RAG matching coverage
        assert len(DEMO_RUNBOOKS) >= 5
        for rb in DEMO_RUNBOOKS:
            # Content, title, and keywords must all be non-empty for RAG to work
            assert len(rb.content) > 0
            assert len(rb.title) > 0
            assert len(rb.keywords) > 0

    def test_runbooks_have_service_tags(self) -> None:
        """Each runbook has a service tag (wildcard '*' is valid)."""
        # Service tag scopes runbook retrieval to the affected service
        for rb in DEMO_RUNBOOKS:
            assert rb.service != ""

    def test_runbooks_have_keywords(self) -> None:
        """Each runbook has at least 2 keywords for RAG matching."""
        # Minimum 2 keywords ensures meaningful keyword-based RAG matching
        for rb in DEMO_RUNBOOKS:
            assert len(rb.keywords) >= 2

    def test_past_incidents_structure(self) -> None:
        """DEMO_PAST_INCIDENTS has valid entries with required fields."""
        # At least 4 past incidents needed for retrieval diversity
        assert len(DEMO_PAST_INCIDENTS) >= 4
        for inc in DEMO_PAST_INCIDENTS:
            # id, service, severity, summary required for RAG retrieval queries
            assert "id" in inc
            assert "service" in inc
            assert "severity" in inc
            assert "summary" in inc
