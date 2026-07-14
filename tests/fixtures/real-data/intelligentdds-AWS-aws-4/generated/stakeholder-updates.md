# Stakeholder Updates

## Update 1
- **Impact:** ELB load balancers in the US-East region are experiencing widespread failures, resulting in high latency, connection timeouts, and service unavailability for customers using ELB. This affects websites, APIs, and applications that rely on ELB for traffic distribution. Many customers in US-East are impacted.
- **Root Cause:** Preliminary analysis indicates a software bug introduced in a recent deployment to the ELB front-end, causing load balancers to enter a processing loop and become unresponsive.
- **Action:** Engineering has identified the bug and is currently rolling back the deployment. A fix is being applied to restore normal operation. Monitoring and validation are ongoing.
- **Next Update:** 2012-12-24 00:05:00+00:00
- **Confidence:** 0.80
- **Status:** ✅ Approved
