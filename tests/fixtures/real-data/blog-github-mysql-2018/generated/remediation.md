# Remediation

## Perform a controlled failback to the original primary MySQL instance after verifying replication lag is minimal and data consistency is confirmed via checksum comparison.
- **Citation:** MySQL Failover Runbook
- **Confidence:** 0.70
- **Expected Outcome:** Database write latency returns to normal within 1 minute, read replica consistency is restored, and GitHub.com page load times improve to pre-incident levels within 5 minutes. No data loss or additional errors expected.
- **Approved:** Yes
