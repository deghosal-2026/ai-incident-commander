# Stakeholder Updates

## Update 1
- **Impact:** All EC2 instances and RDS databases in the US East (Northern Virginia) region are unavailable or severely degraded, affecting a broad set of customers relying on those services for production workloads. Customer-facing applications, data processing, and database access are down.
- **Root Cause:** A network configuration change during a planned scaling activity triggered a cascading failure in the Amazon Elastic Block Store (EBS) control plane, causing widespread loss of connectivity to EC2 instances and RDS databases.
- **Action:** Engineering teams are actively restoring EBS control plane functionality and re-mirroring affected volumes. We are also rolling back the configuration change and implementing additional safeguards to prevent recurrence. No ETA for full recovery yet, but we are working around the clock.
- **Next Update:** 2011-04-29 00:05:00+00:00
- **Confidence:** 0.70
- **Status:** ✅ Approved
