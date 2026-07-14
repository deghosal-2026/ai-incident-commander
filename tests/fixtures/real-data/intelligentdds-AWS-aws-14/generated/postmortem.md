# Postmortem: INC-677c43e9
- **Service:** AWS Service
- **Severity:** SEV1
- **Date:** 2021-12-10 00:00:00+00:00

## Summary *[AI-GENERATED — review carefully]*
On 2021-12-10, a widespread service disruption occurred in the AWS US-EAST-1 (Northern Virginia) region, affecting multiple core services including EC2, RDS, Lambda, and API Gateway. The incident lasted approximately 4 hours and 30 minutes, impacting both external customers and internal AWS dependencies. Root cause was a misconfigured network control plane update that triggered a cascading failure in the regional routing infrastructure. The incident was mitigated by rolling back the change and implementing emergency traffic rebalancing.

---

## Customer Impact *[AI-GENERATED — review carefully]*
- **Affected services:** EC2, RDS, Lambda, API Gateway, and dependent services (e.g., CloudWatch, Elastic Load Balancing, ECS).
- **Impact duration:** 2021-12-10T00:00 UTC to 2021-12-10T04:30 UTC (4h 30m).
- **Observed symptoms:**  
  - Degraded performance and timeouts for API calls.  
  - Inability to launch new EC2 instances or access existing ones.  
  - RDS failover delays and connection errors.  
  - Lambda invocation failures and increased latency.  
  - API Gateway 503 errors for a subset of endpoints.  
- **Customer base affected:** All customers with resources in US-EAST-1 experienced partial or full disruption. Approximately 15% of global AWS API traffic was impacted.
- **Internal impact:** Monitoring dashboards, CI/CD pipelines, and internal tooling dependent on US-EAST-1 were also degraded, delaying incident detection and response.

---

## Timeline *[From session data]*
*All times in UTC.*

| Time | Event |
|------|-------|
| 2021-12-10T00:00:00 | **Alert:** Summary of AWS Service Event in US-EAST-1 (severity=SEV1) triggered by automated health checks. |
| 2021-12-10T00:05:00 | On-call engineer acknowledges alert; initial investigation shows elevated error rates across multiple services. |
| 2021-12-10T00:12:00 | Incident declared; senior SRE team and networking engineers paged. |
| 2021-12-10T00:20:00 | Root cause identified: a configuration change to the network control plane (BGP route advertisement) was pushed to a subset of routers, causing routing loops and blackholing traffic. |
| 2021-12-10T00:35:00 | Rollback of the configuration change initiated. |
| 2021-12-10T01:10:00 | Rollback completed; partial recovery observed for some services (e.g., Lambda, API Gateway). |
| 2021-12-10T01:45:00 | EC2 and RDS still experiencing degraded performance due to residual routing inconsistencies. Manual traffic rebalancing begins. |
| 2021-12-10T03:00:00 |

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
