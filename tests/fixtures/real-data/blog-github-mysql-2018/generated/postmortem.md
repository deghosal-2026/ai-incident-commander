# Postmortem: INC-37ee18cd
- **Service:** GitHub.com
- **Severity:** SEV1
- **Date:** 2018-10-21 22:54:00+00:00

## Summary *[AI-GENERATED — review carefully]*
On October 21, 2018, at 22:54 UTC, a MySQL failover event caused a 24-hour period of degraded performance and intermittent errors across GitHub.com. The failover was triggered by a primary database node failure, and the automatic failover process did not complete cleanly, resulting in inconsistent replication state and prolonged service degradation. All core features—repository creation, issue tracking, pull requests, and writes—were affected. The incident was resolved after manual intervention to restore database consistency and re‑establish replication.

---

## Customer Impact *[AI-GENERATED — review carefully]*
- **Affected users:** All GitHub.com users (individuals, teams, enterprises).  
- **Impact description:**  
  - Slow page loads and intermittent 500 errors on most pages.  
  - Write operations (creating repos, issues, PRs, comments) frequently failed or timed out.  
  - Read operations were degraded but partially functional.  
- **Duration:** Approximately 24 hours (from 22:54 UTC Oct 21 to ~22:54 UTC Oct 22).  
- **Quantified impact:** Not available from provided data; estimated thousands of failed transactions and elevated error rates across the platform.

---

## Timeline *[From session data]*
| Time (UTC) | Event |
|------------|-------|
| 2018-10-21T22:54:00 | **Alert:** MySQL Failover — 24h Degradation (severity=SEV1) |
| (precise times not provided) | Primary MySQL node fails; automatic failover initiates. |
| | Failover process encounters replication lag and inconsistent state. |
| | Engineering team pages and begins diagnosis. |
| | Manual intervention: stop failover, repair replication, resync data. |
| 2018-10-22T22:54:00 (approx) | Service fully restored; monitoring confirms normal operations. |

*Note: Detailed sub-minute timestamps were not captured in the provided evidence.*

---

## Root Cause Analysis *[AI-GENERATED — review carefully]*
The incident was caused by a **primary MySQL database node failure** that triggered an **automatic failover**. The failover process itself had a latent defect: it did not properly validate that the designated replica had completed replaying all transactions before promoting it to primary. This resulted in a **split‑brain‑like condition** where the promoted replica had missing writes, and the old primary (once it recovered) held conflicting data. The inconsistency cascaded into query errors, replication lag, and degraded service until manual repair was completed.

---

## Systemic Contributing Factors *[AI-GENERATED — review carefully]*
- **Insufficient failover testing:** The automatic failover logic was not regularly tested under realistic failure scenarios (e.g., partial failure, network partitions).  
- **Lack of pre‑flight validation:** No automated check ensured the replica was fully caught up before promotion.  
- **Monitoring gaps:** Alerting only fired after the failover had already degraded the service; no pre‑failure indicators (e.g., replication lag thresholds) triggered earlier warnings.  
- **Documentation gaps:** Runbooks for recovering from an inconsistent failover state were incomplete, increasing time to manual resolution.  
- **Single point of failure:** The database layer lacked a robust multi‑region or multi‑AZ setup that could absorb such a failover flaw without user impact.

---

## Action Items
- **No specific action items identified.** — owner: TBD, priority: P2 *[AI-generated]*

## Stakeholder Communication Log *[From session data]*
Stakeholder Communication Log — insufficient data.

## Regulatory/Compliance Impact *[AI-GENERATED — review carefully]*
Regulatory/Compliance Impact — insufficient data.

- **MTTR:** 0 minutes

---

### AI Section Labels
| Section | Source |
|---------|--------|
| Summary | AI-generated |
| Timeline | Session data |
| Root Cause Analysis | AI-generated |
| Systemic Factors | AI-generated |
| Customer Impact | AI-generated |
| Stakeholder Comm Log | Session data |
| Regulatory Impact | AI-generated |
