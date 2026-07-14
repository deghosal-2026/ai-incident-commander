# Remediation

## Implement DNS failover to secondary resolver (e.g., 8.8.8.8) until primary 1.1.1.1 service is restored.
- **Citation:** General DNS outage response runbook
- **Confidence:** 0.70
- **Expected Outcome:** DNS resolution should be restored immediately for all users, with query latency potentially increasing slightly due to different resolver infrastructure. Expected outcome: "DNS query success rate returns to 100% within seconds of failover activation."
- **Approved:** Yes
