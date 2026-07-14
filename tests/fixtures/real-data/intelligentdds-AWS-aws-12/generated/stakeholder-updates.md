# Stakeholder Updates

## Update 1
- **Impact:** Customers are unable to read or write data to Amazon SimpleDB in the affected region (us-east-1). All SimpleDB API calls are returning errors, impacting any applications relying on SimpleDB for storage or querying. This includes both new and existing domains. No data loss is expected, but availability is fully degraded for the service.
- **Root Cause:** Under investigation. Preliminary indications point to a failure in the underlying distributed storage layer that SimpleDB depends on, possibly related to a network partition or a configuration change in the cluster management system.
- **Action:** We have engaged the SimpleDB and core infrastructure engineering teams. We are currently analyzing system logs and metrics to isolate the fault. A rollback of the most recent configuration change is being prepared as a potential mitigation. We will provide an update within 30 minutes.
- **Next Update:** 2014-06-13 00:05:00+00:00
- **Confidence:** 0.30
- **Status:** ✅ Approved
