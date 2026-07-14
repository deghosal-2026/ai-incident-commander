# Stakeholder Updates

## Update 1
- **Impact:** GitLab.com is currently unavailable. All user data (repositories, issues, merge requests, etc.) created or modified in the last 6 hours (approximately 17:00–23:00 UTC on 2017-01-31) has been permanently lost. Users cannot access the service or any data stored on the platform.
- **Root Cause:** Likely a catastrophic database failure (e.g., file system corruption or replication error) that resulted in unrecoverable loss of the primary database and its recent writes. The exact trigger is under investigation.
- **Action:** Engineering teams are actively working to restore service from the last known good backup (taken at ~17:00 UTC). We are also conducting a forensic analysis of the database cluster to determine the root cause and prevent recurrence. An estimated time to recovery will be provided as we assess backup integrity and restoration speed.
- **Next Update:** 2017-01-31 23:05:00+00:00
- **Confidence:** 0.30
- **Status:** ✅ Approved
