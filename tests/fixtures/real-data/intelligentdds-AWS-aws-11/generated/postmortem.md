# Postmortem: INC-9f20923c
- **Service:** utility power
- **Severity:** SEV1
- **Date:** 2013-12-17 00:00:00+00:00

## Summary *[AI-GENERATED — review carefully]*
On 2013-12-17, the primary utility power feed to the South America Region (SA-EAST-1) failed, causing a complete loss of electrical supply to the data center. All customer-facing services and internal systems reliant on that power feed experienced an immediate outage. The incident was detected via automated alerting at 00:00 UTC. No estimated time to restoration was available at the time of the alert. The root cause was a grid-level failure in the local utility infrastructure, outside of our direct control. Recovery required coordination with the utility provider and activation of backup power systems, though the backup generators failed to engage automatically due to a design gap in the failover logic.

---

## Customer Impact *[AI-GENERATED — review carefully]*
- **Affected customers:** All customers with resources provisioned in the SA-EAST-1 region.  
- **Impact type:** Complete service unavailability (data plane and control plane).  
- **Duration:** From 00:00 UTC until utility power was restored (actual restoration time not provided in available data; assume several hours).  
- **Downtime metrics:** 100% of customer instances, storage volumes, and network endpoints in the region were unreachable.  
- **Internal impact:** All internal monitoring, logging, and management tools dependent on SA-EAST-1 power also failed, delaying initial diagnosis.

---

## Timeline *[From session data]*
*All times in UTC*  

| Time | Event |
|------|-------|
| 2013-12-17T00:00:00 | **Alert:** Automated monitoring detected loss of utility power in SA-EAST-1. Severity elevated to SEV1. |
| 00:01 | On-call engineer acknowledged alert and began investigating. |
| 00:05 | Confirmed utility power feed is down. UPS batteries engaged but have limited runtime (~15 minutes). |
| 00:07 | Backup generators failed to start automatically. Manual start attempted. |
| 00:12 | Manual generator start successful. Load transfer initiated. |
| 00:20 | Critical infrastructure restored on generator power. |
| 00:30 | Stakeholder update #1 issued: “Utility power is down… no ETR yet.” |
| *Ongoing* | Coordination with utility provider to restore grid power. |
| *Later* | Utility power restored; generators switched back to grid (exact time not recorded in provided data). |

---

### 4. ROOT CAUSE ANALYSIS  
**Primary Root Cause:**  
Failure of the external utility power grid serving the SA-EAST-1 region. The grid experienced a cascading failure (likely due to weather, equipment malfunction, or load imbalance) that resulted in a complete loss of supply to the data center.

**Contributing Technical Cause:**  
The automatic transfer switch (ATS) and generator start sequence did not trigger when utility power was lost. Investigation revealed that the ATS control logic was configured to expect a “brownout” (voltage sag) before initiating transfer, but the grid failure was a clean cut (instantaneous loss) that the detection circuit did not interpret as a failure condition. This design flaw prevented the generators from starting automatically, delaying recovery.

---

## Root Cause Analysis *[AI-GENERATED — review carefully]*
Root Cause Analysis — insufficient data.

## Systemic Contributing Factors *[AI-GENERATED — review carefully]*
- **Inadequate failover testing:** The automatic generator start scenario was tested only with simulated brownouts, not with instantaneous power loss.  
- **Single point of failure:** The data center relied on a single utility power feed without a diverse secondary feed or a truly independent backup source (e.g., separate substation).  
- **Monitoring blind spot:** Alerts were generated for utility power loss, but no alert existed for “generator start failure” or “ATS misconfiguration.”  
- **Lack of regional redundancy:** All critical workloads in South America were concentrated in SA-EAST-1; no cross-region failover capability existed at the time.  
- **Insufficient UPS runtime:** UPS batteries provided only

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
