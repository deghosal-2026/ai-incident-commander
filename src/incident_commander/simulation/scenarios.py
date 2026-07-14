"""Pre-built incident scenarios for simulation mode."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..models import IncidentInput
from .simulator import IncidentSimulator


class ScenarioConfig(BaseModel):
    """Configuration for a pre-built simulation scenario."""

    name: str  # unique scenario key (must match the dict key in SCENARIOS)
    description: str  # human-readable summary of the scenario
    service: str
    severity: Literal["SEV1", "SEV2", "SEV3"]
    num_logs: int = 15
    num_messages: int = 8
    num_prs: int = 3
    root_cause: str = ""  # machine-readable root cause label for evaluation
    deploy_correlated: bool = False  # True: a recent deploy caused the incident
    # Runbook IDs the analysis engine is expected to match for this scenario
    expected_runbook_matches: list[str] = Field(default_factory=list)


# Each scenario is self-contained with its own parameters; the simulator generates
# realistic log/message/PR data from these config values during load_scenario()
SCENARIOS: dict[str, ScenarioConfig] = {
    # Payment SEV1: DB pool exhaustion during high-traffic event
    "db-connection-pool": ScenarioConfig(
        name="db-connection-pool",
        description="DB connection pool exhaustion causing payment failures",
        service="payment-service",
        severity="SEV1",
        num_logs=20,
        num_messages=12,
        num_prs=2,
        root_cause="db_connection_pool_exhaustion",
        deploy_correlated=True,
        expected_runbook_matches=["rb-001", "rb-002"],
    ),
    # API gateway SEV2: bad deploy introduces misconfigured route
    "bad-deploy": ScenarioConfig(
        name="bad-deploy",
        description="Misconfigured route in API gateway from bad deploy",
        service="api-gateway",
        severity="SEV2",
        num_logs=15,
        num_messages=8,
        num_prs=1,
        root_cause="misconfigured_route",
        deploy_correlated=True,
        expected_runbook_matches=["rb-002"],
    ),
    # Auth service SEV2: undetected memory leak leads to OOM kills
    "memory-leak": ScenarioConfig(
        name="memory-leak",
        description="Gradual memory growth causing OOM kills in auth service",
        service="auth-service",
        severity="SEV2",
        num_logs=10,
        num_messages=5,
        num_prs=1,
        root_cause="memory_leak",
        deploy_correlated=False,
        expected_runbook_matches=["rb-006"],
    ),
    # API gateway SEV1: expired TLS cert causes 502/SSL errors
    "cert-expiry": ScenarioConfig(
        name="cert-expiry",
        description="TLS certificate expired on API gateway",
        service="api-gateway",
        severity="SEV1",
        num_logs=12,
        num_messages=8,
        num_prs=0,
        root_cause="cert_expired",
        deploy_correlated=False,
        expected_runbook_matches=["rb-003"],
    ),
    # Payment SEV1: third-party processor outage (no deploy involved)
    "dependency-outage": ScenarioConfig(
        name="dependency-outage",
        description="Third-party payment API is down",
        service="payment-service",
        severity="SEV1",
        num_logs=18,
        num_messages=10,
        num_prs=0,
        root_cause="third_party_down",
        deploy_correlated=False,
        expected_runbook_matches=[],
    ),
    # Web frontend SEV3: stale config causes incorrect feature flags
    "config-drift": ScenarioConfig(
        name="config-drift",
        description="Stale configuration in web frontend",
        service="web-frontend",
        severity="SEV3",
        num_logs=6,
        num_messages=3,
        num_prs=1,
        root_cause="stale_config",
        deploy_correlated=False,
        expected_runbook_matches=[],
    ),
    # Product catalog SEV2: stale cache serves outdated product data
    "cache-invalidation": ScenarioConfig(
        name="cache-invalidation",
        description="Stale cache returns incorrect product data",
        service="product-catalog",
        severity="SEV2",
        num_logs=10,
        num_messages=6,
        num_prs=0,
        root_cause="stale_cache",
        deploy_correlated=False,
        expected_runbook_matches=["rb-004"],
    ),
    # Search service SEV3: upstream API rate-limit degrades results
    "rate-limit-hit": ScenarioConfig(
        name="rate-limit-hit",
        description="Upstream rate limit exceeded causing degraded search",
        service="search-service",
        severity="SEV3",
        num_logs=8,
        num_messages=4,
        num_prs=0,
        root_cause="rate_limit_exceeded",
        deploy_correlated=False,
        expected_runbook_matches=["rb-005"],
    ),
}


def load_scenario(name: str, seed: int = 42) -> IncidentInput:  # seed=42 for reproducibility
    """Load a pre-built scenario and return fully generated IncidentInput."""
    if name not in SCENARIOS:
        # list available scenario keys so users can fix typos
        raise KeyError(f"Unknown scenario: {name}. Available: {list(SCENARIOS.keys())}")

    cfg = SCENARIOS[name]
    simulator = IncidentSimulator(seed=seed)
    # generate the full incident dataset from the scenario's parameters
    return simulator.simulate(
        service=cfg.service,
        severity=cfg.severity,
        num_logs=cfg.num_logs,
        num_messages=cfg.num_messages,
        num_prs=cfg.num_prs,
        deploy_correlated=cfg.deploy_correlated,
    )
