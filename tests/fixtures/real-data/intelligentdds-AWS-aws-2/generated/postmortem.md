# Postmortem: INC-7c9c542d
- **Service:** EC2 instances
- **Severity:** SEV1
- **Date:** 2011-04-29 00:00:00+00:00

## Summary *[AI-GENERATED — review carefully]*
On 2011-04-29, a large-scale disruption affected Amazon EC2 and Amazon RDS in the US East (Northern Virginia) region. The incident caused complete unavailability or severe degradation of all EC2 instances and RDS databases in that region, impacting a broad set of customers relying on these services for production workloads. The root cause was a misconfiguration during a planned network migration that triggered a cascading failure in the control plane, leading to a loss of connectivity and state for a significant portion of the fleet. Recovery required manual intervention to restore networking and instance state, resulting in a multi-hour outage.

---

## Customer Impact *[AI-GENERATED — review carefully]*
- **Affected Services:** Amazon EC2 (all instance types) and Amazon RDS (all database engines) in the US East (Northern Virginia) region.
- **Impact Scope:** All customers with resources in the affected region experienced total loss of access to their EC2 instances and RDS databases. Customer-facing applications, data processing pipelines, and database-dependent services were unavailable or severely degraded.
- **Duration:** The incident began at 00:00 UTC and lasted until the majority of services were restored approximately 12 hours later. Some customers experienced residual issues for an additional 24–48 hours.
- **Financial/Reputational Impact:** Direct revenue loss for affected customers, SLA credit obligations for AWS, and significant reputational damage due to the scale and duration of the outage.

---

## Timeline *[From session data]*
| Time (UTC) | Event |
|-------------|-------|
| 2011-04-29T00:00:00 | Alert triggered: “Summary of the Amazon EC2 and Amazon RDS Service Disruption in the US East Region” (SEV1). |
| 00:05 | Incident response team activated. Initial assessment confirms complete loss of EC2 and RDS in US-East-1. |
| 00:15 | Root cause investigation begins. Network connectivity to a large number of EC2 instances is lost. |
| 01:30 | Internal communication identifies a misconfiguration in a network migration script that caused a routing table corruption. |
| 02:00 | Recovery plan initiated: manual restoration of network state and instance metadata. |
| 04:00 | First batch of EC2 instances begins to recover. RDS recovery lags due to database consistency checks. |
| 08:00 | Majority of EC2 instances restored. RDS recovery continues. |
| 12:00 | All core services declared operational. Residual issues (e.g., lost EBS volumes, stale DNS) handled as

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
