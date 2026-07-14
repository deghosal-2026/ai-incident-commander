"""IncidentSimulator — generates fake alerts, logs, messages, and PRs."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Literal

from ..models import (
    Alert,
    ChatMessage,
    GitHubPR,
    IncidentInput,
    IncidentMeta,
    LogEntry,
)
from .demo_runbooks import DEMO_RUNBOOKS

# Valid severity tiers for simulated alerts (SEV1=critical, SEV3=minor)
SEVERITY_LABELS: list[Literal["SEV1", "SEV2", "SEV3"]] = ["SEV1", "SEV2", "SEV3"]

# Log levels the simulator can assign to generated log entries
LOG_LEVELS: list[Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "TRACE"]] = [
    "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "TRACE"
]

# Nine fake microservices used across all simulation scenarios
SERVICES = [
    "payment-service", "api-gateway", "auth-service",
    "web-frontend", "product-catalog", "search-service",
    "order-service", "worker-service", "image-processor",
]


class IncidentSimulator:
    """Generates fake alerts, logs, messages, and PRs for simulation mode."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the simulator with an optional seed for reproducibility."""
        # seed=None → non-deterministic (system entropy); int → reproducible across runs
        self._rng = random.Random(seed)

    def _generate_alert(
        self, service: str, severity: str, base_time: datetime
    ) -> Alert:
        """Generate a simulated alert with a random summary template matching severity."""
        # Per-severity alert summary templates; one is chosen at random
        summaries = {
            "SEV1": [
                "Service is down — all requests failing",
                f"Critical: {service} unreachable",
                "Error rate exceeds 5% threshold — customer impact confirmed",
            ],
            "SEV2": [
                f"{service} latency > 2 seconds (p99)",
                f"Intermittent errors on {service}",
                f"{service} degraded — partial outage suspected",
            ],
            "SEV3": [
                f"{service} error rate elevated (0.5%)",
                f"Warning: {service} p99 latency > 1 second",
                f"Minor degradation detected on {service}",
            ],
        }
        # Fallback to SEV3 templates if severity is unrecognized
        summary = self._rng.choice(summaries.get(severity, summaries["SEV3"]))
        return Alert(
            severity=severity,  # type: ignore
            service=service,
            summary=summary,
            source="simulated",
            timestamp=base_time,
            # ID format: SIM-YYYYMMDD-NNN — date + random 3-digit suffix for uniqueness
            incident_id=f"SIM-{base_time.strftime('%Y%m%d')}-{self._rng.randint(100, 999)}",
        )

    def _generate_logs(
        self, service: str, base_time: datetime, count: int,
    ) -> list[LogEntry]:
        """Generate simulated log entries transitioning from INFO to WARN to ERROR."""
        logs: list[LogEntry] = []
        error_messages = [  # messages used for WARN/ERROR entries (symptoms + failures)
            f"Connection pool exhausted for {service}",
            f"Timeout connecting to upstream {service}",
            "HTTP 500 Internal Server Error",
            "Database query timeout after 30s",
            "Memory usage exceeding threshold (85%)",
            "Failed to acquire lock — deadlock detected",
            "TLS handshake failed: certificate expired",
            f"Rate limit exceeded for upstream API ({service})",
            "Cache miss cascade detected — 3x query load",
        ]
        info_messages = [  # benign messages for normal INFO entries
            f"Health check passed for {service}",
            "Configuration reloaded successfully",
            f"Connection pool restored for {service}",
            "Circuit breaker closed — normal operation",
            "Cache warming completed",
        ]
        # Log arc: INFO → WARN → ERROR — simulates the natural progression toward an incident
        for i in range(count):
            ts = base_time - timedelta(minutes=count - i)  # oldest -> newest as i grows
            if i < count - 3:  # early logs: normal INFO entries
                level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "TRACE"] = "INFO"
                msg = self._rng.choice(info_messages)
            elif i < count - 1:  # second-to-last: WARN (early symptom)
                level = "WARN"
                msg = f"Warning: {error_messages[i % len(error_messages)]}"
            else:  # last entry: ERROR (the failure that triggered the alert)
                level = "ERROR"
                msg = error_messages[i % len(error_messages)]
            logs.append(
                LogEntry(timestamp=ts, level=level, message=msg, source=service)
            )
        return logs

    def _generate_messages(
        self, service: str, base_time: datetime, count: int,
    ) -> list[ChatMessage]:
        """Generate simulated chat messages tracing the incident arc."""
        authors = ["alice", "bob", "charlie", "diana"]
        # Templates trace the incident arc: discovery -> investigation -> rollback -> recovery
        message_templates = [
            "Anyone else seeing errors on {service}?",
            "Error rate spiking on {service}",
            "Checking logs now...",
            "Could be related to the recent deploy",
            "I see connection timeouts in the logs",
            "Rolling back PR to be safe",
            "Confirming — rollback in progress",
            "Error rate dropping after rollback",
        ]
        messages: list[ChatMessage] = []
        for i in range(count):
            ts = base_time - timedelta(minutes=count - i)  # oldest -> newest
            # Templates are cycled (not random) so the message arc is deterministic per seed
            text = message_templates[i % len(message_templates)].format(service=service)
            messages.append(
                ChatMessage(
                    timestamp=ts,
                    author=self._rng.choice(authors),
                    text=text,
                    channel="#incidents",  # all simulated chat in one channel
                )
            )
        return messages

    def _generate_prs(
        self, service: str, base_time: datetime, count: int,
        before_alert: bool = True,  # True: PRs merged before alert (deploy is suspected cause)
    ) -> list[GitHubPR]:
        """Generate simulated GitHub PRs — either before alert (suspected cause) or after (fix)."""
        prs: list[GitHubPR] = []
        pr_titles = [
            f"fix: resolve connection pool leak in {service}",
            f"chore: update dependency versions for {service}",
            f"feat: add retry logic to {service}",
            f"fix: correct timeout configuration in {service}",
            f"chore: bump {service} to v2.1.0",
        ]
        authors = ["dev-user-1", "dev-user-2", "dev-user-3"]
        for i in range(count):
            if before_alert:
                # Deploy before alert: merged 5-60 min before the incident (suspected cause)
                merge_time = base_time - timedelta(minutes=self._rng.randint(5, 60))
            else:
                # Deploy after alert: merged 1-30 min after (fix PR, not cause)
                merge_time = base_time + timedelta(minutes=self._rng.randint(1, 30))
            prs.append(
                GitHubPR(
                    number=1000 + i,  # fake PR numbers start at 1000
                    title=pr_titles[i % len(pr_titles)],
                    author=self._rng.choice(authors),
                    merge_time=merge_time,
                    files_changed=[
                        f"src/{service}/main.py",
                        f"src/{service}/config.py",
                    ],
                    labels=["deploy"],  # all sim PRs tagged "deploy" for filtering
                )
            )
        return prs

    def simulate(
        self,
        service: str,
        severity: str,
        num_logs: int = 15,
        num_messages: int = 8,
        num_prs: int = 3,
        deploy_correlated: bool = True,  # True: PRs before alert (deploy caused incident)
    ) -> IncidentInput:
        """Generate a complete simulated incident dataset."""
        # All generated timestamps are relative to this anchor; alerts/logs/messages are backdated
        base_time = datetime.now()

        alert = self._generate_alert(service, severity, base_time)
        logs = self._generate_logs(service, base_time, num_logs)
        messages = self._generate_messages(service, base_time, num_messages)
        prs = self._generate_prs(service, base_time, num_prs, before_alert=deploy_correlated)

        # Metadata envelope describing the incident for downstream analysis
        meta = IncidentMeta(
            incident_id=alert.incident_id,
            service=service,
            severity=alert.severity,
            # Incident start is 5 minutes before the alert — simulates the detection gap
            start_time=base_time - timedelta(minutes=5),
            description=f"Simulated {severity} incident on {service}",
            commander="sim-commander",
            oncall_roster=["alice", "bob"],
            # Tags combine simulation marker + service + severity for downstream filtering
            tags=["simulated", service, severity.lower()],
        )

        # Assemble the full incident dataset consumed by the analysis pipeline
        return IncidentInput(
            alert=alert,
            logs=logs,
            messages=messages,
            github=prs,
            runbooks=DEMO_RUNBOOKS,
            meta=meta,
        )
