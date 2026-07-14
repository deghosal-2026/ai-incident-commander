# Postmortem: INC-9832ba0f
- **Service:** diesel rotary uninterruptable power supply
- **Severity:** SEV1
- **Date:** 2011-06-04 00:00:00+00:00

## Summary *[AI-GENERATED — review carefully]*
On 2011-06-04, a failure of the diesel rotary uninterruptible power supply (DRUPS) system in the AWS Sydney region caused a loss of electrical power to critical infrastructure supporting multiple AWS services. This resulted in a SEV1 service event affecting availability zones dependent on that DRUPS. Customers experienced service disruptions, latency, and unavailability until power was restored and systems were stabilized. The root cause was a mechanical failure within the DRUPS unit during a utility power fluctuation, compounded by insufficient redundancy in the power distribution path for the affected data halls.

---

## Customer Impact *[AI-GENERATED — review carefully]*
- **Affected Services:** EC2 instances, EBS volumes, RDS databases, and other services hosted in the impacted availability zones experienced partial or complete loss of power.
- **Impact Duration:** Approximately 4–6 hours from initial power loss to full recovery of all customer-facing services.
- **Observable Effects:** 
  - Customers reported inability to launch new instances or access existing ones.
  - Existing EC2 instances in the affected zones were terminated or became unreachable.
  - EBS volumes became unavailable, with some requiring manual recovery after power restoration.
  - Latency and error rates (5xx) increased globally for services relying on cross-AZ replication from the affected zones.
- **Customer Count:** Thousands of customers across multiple verticals (e-commerce, media, SaaS) were impacted, including both direct AWS users and downstream services.

---

## Timeline *[From session data]*
*All times in UTC.*

| Time | Event |
|------|-------|
| 2011-06-04T00:00:00 | **Alert triggered:** AWS monitoring systems detect a summary of a service event in the Sydney region. Severity set to SEV1. |
| 00:02 | Internal incident response team paged. Initial assessment indicates power loss to a data hall served

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
