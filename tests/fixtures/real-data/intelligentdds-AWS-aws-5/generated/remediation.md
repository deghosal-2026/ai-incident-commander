# Remediation

## Enable DynamoDB Global Tables to replicate critical tables to a secondary AWS region (e.g., US-West-2) and configure application-level failover to that region.
- **Citation:** DynamoDB Disaster Recovery Runbook – Section 4.2: Multi-Region Failover
- **Confidence:** 0.70
- **Expected Outcome:** Application availability for critical tables should recover within 5–10 minutes of initiating failover, with eventual consistency across regions.
- **Approved:** Yes
