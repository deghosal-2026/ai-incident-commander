# Remediation

## Restore database from the most recent full backup and apply all available WAL archives up to the point of failure, then validate data integrity and resume service.
- **Citation:** GitLab Database Recovery Runbook (db-recovery)
- **Confidence:** 0.80
- **Expected Outcome:** Data loss should be fully recovered; GitLab.com service should resume with no data gap after restore and validation, typically within 1-3 hours.
- **Similar Incidents:** INC-2022-11-20, INC-2023-03-05
- **Approved:** Yes
