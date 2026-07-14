# Stakeholder Updates

## Update 1
- **Impact:** All Cloudflare customers are unable to access the Cloudflare dashboard, manage configurations, or view analytics. API calls to the control plane are also failing. This affects configuration changes, DNS edits, and real-time analytics visibility. No impact on edge traffic or existing security rules.
- **Root Cause:** Currently unknown. Initial alerts indicate a widespread control plane service degradation; investigation is ongoing.
- **Action:** Engineering teams are actively investigating. We have paged all relevant on-call engineers and are reviewing recent deployments, infrastructure metrics, and logs to identify the failure point. A rollback is being prepared if a recent change is identified.
- **Next Update:** 2023-11-02 11:49:00+00:00
- **Confidence:** 0.20
- **Status:** ✅ Approved
