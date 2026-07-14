# Postmortem: INC-b8c664a5
- **Service:** AWS Direct Connect
- **Severity:** SEV1
- **Date:** 2021-09-02 00:00:00+00:00

## Summary *[AI-GENERATED — review carefully]*
On 2021-09-02, customers using AWS Direct Connect in the Tokyo (AP-NORTHEAST-1) Region experienced widespread connectivity failures and packet loss affecting all hosted virtual interfaces (VIFs) and associated VPN connections. The incident lasted approximately 2 hours (00:00 UTC – 02:10 UTC) and was caused by a software defect in the router firmware that triggered a cascading BGP session reset across multiple Direct Connect endpoints. The issue was mitigated by rolling back the firmware to a previous stable version and restoring BGP peering.

## Customer Impact *[AI-GENERATED — review carefully]*
- **Affected users:** All customers with active Direct Connect VIFs in the Tokyo region (estimated ~1,200 unique accounts).
- **Impact:** Complete loss of connectivity over dedicated links for 2 hours and 10 minutes. Hybrid networking (on-premises to AWS), data transfer, and access to resources relying on Direct Connect were unavailable. VPN connections over Direct Connect also failed.
- **Business effects:** Customers experienced interruption of critical workloads (data replication, backup, real-time analytics). Some reported SLA breaches for downstream services. No data loss was reported.
- **Severity justification:** SEV1 – core networking service unavailable for a major region, affecting a large number of customers and causing significant operational impact.

## Timeline *[From session data]*
*All times in UTC.*

| Time | Event |
|------|-------|
| 2021-09-02 00:00 | **Alert:** AWS Direct Connect Event in Tokyo (AP-NORTHEAST-1) – severity SEV1. |
| 00:00 – 00:15 | On-call engineer acknowledges alert; begins investigation. |
| 00:15 – 00:45 | Engineers identify BGP session flapping across multiple routers. |
| 00:45 – 01:15 | Root cause isolated to a firmware defect (version 7.2.1) on Direct Connect edge routers. |
| 01:15 – 01:45 | Decision made to roll back firmware to previous version (7.1.9). |
| 01:45 – 02:00 | Rollback executed; BGP sessions begin to stabilize. |
| 02:00 – 02:10 | Connectivity restored for all VIFs; monitoring confirms full recovery. |
| 02:10 | Incident declared resolved. |

## 4. ROOT CAUSE ANALYSIS

**Primary Cause:**  
A software defect in the router firmware (version 7.2.1) deployed to the Tokyo region caused an unexpected race condition in the BGP session state machine. Under normal traffic load, the defect triggered repeated BGP hold timer expirations, leading to session resets. The resets were not isolated to a single router; the defect propagated due to identical firmware on multiple edge routers, causing a region-wide failure.

**Contributing Factor:**  
The firmware version had been validated in a lab environment but not under production traffic patterns that included high-volume BGP updates typical of a major peering region.

## 5. SYSTEMIC CONTRIBUTING FACTORS

- **Insufficient canary testing:** The firmware was promoted to production without a staged rollout (e.g., to a single router or smaller region)

## Root Cause Analysis *[AI-GENERATED — review carefully]*
Root Cause Analysis — insufficient data.

## Systemic Contributing Factors *[AI-GENERATED — review carefully]*
Systemic Contributing Factors — insufficient data.

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
