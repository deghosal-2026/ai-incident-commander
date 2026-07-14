# Stakeholder Updates

## Update 1
- **Impact:** Widespread disruption to AWS services in US-EAST-1, including EC2, RDS, Lambda, and API Gateway. Affected customers report degraded performance, timeouts, and inability to launch or access resources. Internal and external dependencies (e.g., monitoring, CI/CD pipelines) are impacted.
- **Root Cause:** Preliminary investigation suggests a network control plane issue within the US-EAST-1 region, potentially related to a misconfiguration or hardware fault in the underlying infrastructure.
- **Action:** AWS engineering teams are actively engaged in diagnosing and mitigating the issue. We are rerouting traffic to healthy partitions and scaling control plane capacity. No ETA for full recovery; updates every 30 minutes.
- **Next Update:** 2021-12-10 00:05:00+00:00
- **Confidence:** 0.40
- **Status:** ✅ Approved
