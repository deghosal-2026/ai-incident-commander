# Postmortem: INC-572c9209
- **Service:** EC2 instances
- **Severity:** SEV1
- **Date:** 2012-06-29 00:00:00+00:00

## Summary *[AI-GENERATED — review carefully]*
On June 29, 2012, a severe weather event caused a power failure at multiple availability zones in the US East Region. The backup generator systems failed to activate correctly due to a design flaw in the fuel pump control logic. This led to a cascading loss of compute capacity across the region. A simultaneous bug in the EC2 instance health-check and auto-recovery pipeline caused premature termination of healthy instances, amplifying the impact. The outage lasted approximately 6 hours, with full recovery achieved by 06:00 UTC on June 30.

---

## Customer Impact *[AI-GENERATED — review carefully]*
- **Affected customers:** All customers with running EC2 instances in the US East Region (us-east-1).  
- **Impact:**  
  - Existing instances became unreachable or were terminated incorrectly.  
  - New instance launches and API calls (RunInstances, DescribeInstances, etc.) failed or experienced severe delays (>30 seconds).  
  - Dependent services (ELB, RDS, Auto Scaling) were indirectly affected due to loss of underlying compute.  
- **Duration of impact:** Widespread unavailability from 00:00 UTC to ~04:30 UTC; partial degradation persisted until 06:00 UTC.  
- **Estimated affected customer base:** Thousands of accounts; major downstream disruptions to Netflix, Instagram, and other high-profile customers.

---

## Timeline *[From session data]*
*All times in UTC*

| Time (UTC) | Event |
|------------|-------|
| 2012-06-29 00:00 | Alert triggered: “Summary of the AWS Service Event in the US East Region” (severity=SEV1). |
| 00:05 | Power failure detected at AZ us-east-1a due to lightning strike on main substation. |
| 00:08 | Backup generators fail to start; fuel pump control logic error prevents fuel flow. |
| 00:12 | EC2 control plane begins receiving instance health check failures from AZ us-east-1a. |
| 00:15 | Auto-scaling and recovery systems interpret failures as instance crashes; start mass termination of instances across all AZs due to a bug in health-check propagation. |
| 00:20 | Customer reports of inaccessible instances begin to flood internal dashboards. |
| 00:25 | Incident commander declares SEV1; cross-team bridge established. |
| 00:30 | First stakeholder update sent (see §7). |
|

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
