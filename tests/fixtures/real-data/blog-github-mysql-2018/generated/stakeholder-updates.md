# Stakeholder Updates

## Update 1
- **Impact:** GitHub.com is experiencing degraded performance and intermittent errors due to a MySQL failover event. All users may encounter slow page loads, failed writes, and occasional 500 errors. Core functionality—including repository creation, issue tracking, and pull requests—is affected.
- **Root Cause:** A MySQL primary database failed over to a replica. The root cause of the failover is under investigation; initial indicators point to a hardware fault or replication lag.
- **Action:** Our database engineering team has initiated an emergency failback procedure to restore the primary. We are monitoring replication health and scaling up read replicas to mitigate load. Incident response is actively triaging and will provide another update within 30 minutes or when significant progress is made.
- **Next Update:** 2018-10-21 22:59:00+00:00
- **Confidence:** 0.40
- **Status:** ✅ Approved
