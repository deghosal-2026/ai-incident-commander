"""Pre-indexed demo runbooks for simulation mode."""

from typing import Any

from ..models import Runbook

# Pre-indexed runbooks available to the simulator for runbook matching
DEMO_RUNBOOKS: list[Runbook] = [
    Runbook(
        id="rb-001",
        title="DB Connection Pool Exhaustion",
        path="runbooks/payment-service/db-connection-pool.md",
        content=(
            "## Triage\n"
            "1. Check active connections: `SELECT count(*) FROM pg_stat_activity`\n"
            "2. Check idle-in-transaction: "
            "`SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction'`\n"
            "3. Kill long-running queries: "
            "`SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE state = 'active' AND now() - pg_stat_activity.query_start "
            "> interval '5 minutes'`\n"
            "## Remediation\n"
            "- Increase max_connections in postgresql.conf\n"
            "- Add connection pooling (PgBouncer)\n"
            "- Rollback recent deploy if pool exhaustion correlates with PR"
        ),
        keywords=["db", "connection", "pool", "exhaustion", "timeout", "postgres"],
        service="payment-service",
    ),
    # Generic rollback procedure for deploy-related incidents
    # "service": "*" = wildcard — this runbook matches any service
    Runbook(
        id="rb-002",
        title="Standard Rollback Procedure",
        path="runbooks/standard/rollback-procedure.md",
        content=(
            "## Prerequisites\n"
            "- Identify the PR that caused the issue\n"
            "- Ensure rollback doesn't break DB migrations\n"
            "## Procedure\n"
            "1. `git revert <merge-commit-hash>`\n"
            "2. Create rollback PR\n"
            "3. Get code review (fast-track for SEV1)\n"
            "4. Deploy rollback to staging, verify\n"
            "5. Deploy to production\n"
            "6. Monitor error rates for 15 minutes"
        ),
        keywords=["rollback", "deploy", "revert", "pr", "production"],
        service="*",  # Wildcard — matched against any service, not a specific one
    ),
    # Handles expired TLS certificates on the API gateway
    Runbook(
        id="rb-003",
        title="TLS Certificate Renewal",
        path="runbooks/infrastructure/cert-renewal.md",
        content=(
            "## Detection\n"
            "- Alert: `x509: certificate has expired or is not yet valid`\n"
            "- Check expiry: "
            "`openssl s_client -connect <host>:443 -servername <host> "
            "2>/dev/null | openssl x509 -noout -dates`\n"
            "## Remediation\n"
            "1. Generate new cert: `certbot certonly --standalone -d <domain>`\n"
            "2. Update TLS secret in Kubernetes\n"
            "3. Restart ingress pods to pick up new cert\n"
            "4. Verify: `curl -I https://<domain>`"
        ),
        keywords=["tls", "cert", "certificate", "expiry", "ssl", "ingress"],
        service="api-gateway",
    ),
    # Handles stale cache in product-catalog (Redis)
    Runbook(
        id="rb-004",
        title="Cache Invalidation",
        path="runbooks/product-catalog/cache-clear.md",
        content=(
            "## Detection\n"
            "- Stale data returned by API\n"
            "- Cache hit rate drops suddenly\n"
            "## Procedure\n"
            "1. Identify cache keys: check application logs for cache key patterns\n"
            "2. Flush specific keys: `redis-cli DEL <key>`\n"
            "3. If widespread: `redis-cli FLUSHDB` (caution: clears entire DB)\n"
            "4. Verify: check fresh data returned\n"
            "5. Root cause: fix cache TTL configuration"
        ),
        keywords=["cache", "redis", "invalidation", "stale", "ttl"],
        service="product-catalog",
    ),
    # Handles upstream rate-limit (HTTP 429) in search-service
    Runbook(
        id="rb-005",
        title="Rate Limit Negotiation",
        path="runbooks/integrations/rate-limit-negotiation.md",
        content=(
            "## Detection\n"
            "- HTTP 429 responses\n"
            "- Error: `rate limit exceeded`\n"
            "## Procedure\n"
            "1. Identify upstream service from error message\n"
            "2. Check current rate limit in config\n"
            "3. Contact upstream team to negotiate limit increase\n"
            "4. Implement backoff: exponential backoff with jitter\n"
            "5. Add caching to reduce API calls\n"
            "6. Monitor: track 429 rate after changes"
        ),
        keywords=["rate", "limit", "429", "throttle", "backoff"],
        service="search-service",
    ),
    # Handles memory leaks / OOM kills in containerized services
    Runbook(
        id="rb-006",
        title="Memory Leak Investigation",
        path="runbooks/image-processor/memory-leak.md",
        content=(
            "## Detection\n"
            "- Gradual memory increase in container metrics\n"
            "- OOMKilled events in pod status\n"
            "## Investigation\n"
            "1. `kubectl top pods` — check current memory usage\n"
            "2. Heap dump: `jmap -heap <pid>`\n"
            "3. Check for unreleased resources in code\n"
            "4. Compare with recent deployments\n"
            "## Remediation\n"
            "- Increase memory limits temporarily\n"
            "- Rollback recent code changes\n"
            "- Add memory leak detection to CI"
        ),
        keywords=["memory", "leak", "oom", "heap", "pod", "container"],
        service="image-processor",
    ),
]


# Past incidents for RAG retrieval (wired in S4)
# Each incident maps to a demo runbook via shared keywords; the engine retrieves
# these during analysis to suggest resolutions based on historical patterns
DEMO_PAST_INCIDENTS: list[dict[str, Any]] = [
    # DB pool exhaustion in payment-service — resolved by rollback (matches rb-001)
    {
        "id": "INC-2025-088",
        "service": "payment-service",
        "severity": "SEV1",
        "date": "2025-11-15",
        "summary": "DB connection pool exhaustion. Resolved by rollback.",
        "resolution": "Rolled back PR #4521. Connection pool size increased.",
        "keywords": ["db", "connection", "pool", "rollback"],
    },
    # TLS cert expiry on api-gateway — renewed via certbot (matches rb-003)
    {
        "id": "INC-2025-112",
        "service": "api-gateway",
        "severity": "SEV2",
        "date": "2025-12-03",
        "summary": "TLS certificate expired, causing 502 errors.",
        "resolution": "Renewed cert via certbot, updated Kubernetes secret.",
        "keywords": ["tls", "cert", "expired", "502"],
    },
    # Memory leak in auth-service — OOM every 20 min, fixed by rollback (rb-006)
    {
        "id": "INC-2026-007",
        "service": "auth-service",
        "severity": "SEV1",
        "date": "2026-01-10",
        "summary": "Memory leak caused OOM kills every 20 minutes.",
        "resolution": "Rolled back PR #4892. Memory limit increased temporarily.",
        "keywords": ["memory", "leak", "oom", "auth"],
    },
    # Stale config in web-frontend — incorrect feature flag state
    {
        "id": "INC-2026-021",
        "service": "web-frontend",
        "severity": "SEV3",
        "date": "2026-02-14",
        "summary": "Stale config caused incorrect feature flag state.",
        "resolution": "Config reloaded. Added staleness check to deployment pipeline.",
        "keywords": ["config", "stale", "feature", "flag"],
    },
    # Rate limit on search upstream — fixed with backoff + caching (rb-005)
    {
        "id": "INC-2026-045",
        "service": "search-service",
        "severity": "SEV3",
        "date": "2026-03-22",
        "summary": "Upstream rate limit exceeded, degrading search results.",
        "resolution": "Implemented exponential backoff. Cached frequent queries.",
        "keywords": ["rate", "limit", "upstream", "search"],
    },
    # Third-party payment processor degradation — circuit breaker opened
    {
        "id": "INC-2026-052",
        "service": "payment-service",
        "severity": "SEV2",
        "date": "2026-04-01",
        "summary": "Third-party payment processor degraded, circuit breaker opened.",
        "resolution": "Circuit breaker threshold adjusted. Vendor notified.",
        "keywords": ["third-party", "payment", "circuit-breaker"],
    },
]
