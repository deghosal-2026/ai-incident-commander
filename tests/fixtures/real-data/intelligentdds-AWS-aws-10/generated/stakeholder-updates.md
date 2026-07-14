# Stakeholder Updates

## Update 1
- **Impact:** A subset of EBS volumes in the US-East Region are experiencing degraded performance and intermittent unavailability, affecting EC2 instances that rely on those volumes. Customers may see increased latency, I/O errors, or inability to attach/detach volumes.
- **Root Cause:** Under investigation. Preliminary indicators point to a storage backend subsystem failure, but the exact cause has not yet been confirmed.
- **Action:** Our engineering team is actively triaging the event, with on-call responders analyzing system logs and metrics. We have initiated mitigation steps to isolate the affected storage nodes and restore normal operation for impacted volumes.
- **Next Update:** 2012-10-22 00:05:00+00:00
- **Confidence:** 0.30
- **Status:** ✅ Approved
