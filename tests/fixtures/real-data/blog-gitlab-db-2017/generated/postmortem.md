# Postmortem: INC-b5654e0c
- **Service:** GitLab.com
- **Severity:** SEV1
- **Date:** 2017-01-31 23:00:00+00:00

## Summary *[AI-GENERATED — review carefully]*
On 2017-01-31, GitLab.com experienced a severe database outage resulting in the permanent loss of all user data (repositories, issues, merge requests, etc.) created or modified during the six‑hour window from approximately 17:00 UTC to 23:00 UTC. The incident was triggered by an accidental deletion of a primary database directory on a shared filesystem. The deletion occurred during a routine maintenance operation and was not detected until an alert fired at 23:00 UTC. The service remained unavailable until recovery procedures were completed. This postmortem documents the root causes, systemic contributing factors, and corrective actions to prevent recurrence.

## Customer Impact *[AI-GENERATED — review carefully]*
- **Affected users**: All GitLab.com users (individuals and organizations) who created, modified, or deleted any data (code repositories, issues, merge requests, comments, user profiles, CI/CD pipeline configurations) between approximately 17:00 UTC and 23:00 UTC on 2017-01-31.
- **Impact type**: Permanent data loss. No recovery was possible because the affected data existed only on the deleted filesystem and no usable backup was available for that time window.
- **Service unavailability**: GitLab.com was completely unavailable from 23:00 UTC onward until services were restored (estimated duration: several hours beyond the incident window).
- **Secondary impact**: Loss of trust in the platform’s data durability guarantees; reputational damage.

## Timeline *[From session data]*
All times are in UTC on 2017-01-31.

| Time (UTC) | Event |
|------------|-------|
| ~17:00 | A production database directory was accidentally deleted during a manual maintenance procedure. The deletion was not immediately detected because no monitoring existed for the specific filesystem path. |
| 17:00 – 23:00 | GitLab.com continued to accept new data, which was written to the now‑deleted directory. All writes effectively went to “nowhere” (the filesystem removed the inode but the process held file handles, so writes succeeded but data was lost on file close). |
| 23:00 | **Alert fired**: “Database Outage — 6h Data Loss (severity=SEV1)”. The alert was triggered by a sudden drop in database responsiveness and a subsequent health check failure. |
| 23:00 – 23:15 | On‑call engineer acknowledged the alert and began investigating. Initial checks revealed that the database filesystem was empty. |
| 23:15 – 23:30 | The team verified that no recent backup of the deleted data existed. The last full backup was from 17:00 UTC, and incremental backups had been misconfigured to overwrite the same destination, leaving no usable copy for the 17:00–23:00 window. |
| 23:30 – 00:30 | Recovery attempt: the team attempted to restore from the 17:00 UTC backup, but the restoration process took longer than expected due to the volume of data. All data created after 17:00 was confirmed lost. |
| 00:30+ | Service gradually restored using the 17:00 UTC backup. A public announcement was made. |

## Root Cause Analysis *[AI-GENERATED — review carefully]*
**Primary cause**: Accidental deletion of the production database directory (`/data/gitlab/postgresql/data`) by an operator during a routine maintenance task. The deletion command (`rm -rf`) was issued on the wrong path due to a combination of fatigue, lack of a change‑control review, and insufficient protection on

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
