# Application Logs - Troubleshooting
### No Logs Arrive at the Backend
**Symptom**:
- No logs arrive at the backend.
- In the LogPipeline status, the `TelemetryFlowHealthy` condition has status **AllDataDropped**.
**Cause**: Incorrect backend endpoint configuration (for example, using the wrong authentication credentials) or the backend being unreachable.
**Solution**:
- Check the `telemetry-fluent-bit` Pods for error logs by calling `kubectl logs -n kyma-system {POD_NAME}`.
- Check if the backend is up and reachable.
### Not All Logs Arrive at the Backend
**Symptom**:
- The backend is reachable and the connection is properly configured, but some logs are refused.
- In the LogPipeline status, the `TelemetryFlowHealthy` condition has status **SomeDataDropped**.
**Cause**: It can happen due to a variety of reasons. For example, a possible reason may be that the backend is limiting the ingestion rate, or the backend is refusing logs because they are too large.
**Solution**:
1. Check the `telemetry-fluent-bit` Pods for error logs by calling `kubectl logs -n kyma-system {POD_NAME}`. Also, check your observability backend to investigate potential causes.
2. If backend is limiting the rate by refusing logs, try the options described in [Agent Buffer Filling Up](#agent-buffer-filling-up).
3. Otherwise, take the actions appropriate to the cause indicated in the logs.
### Agent Buffer Filling Up
**Symptom**: In the LogPipeline status, the `TelemetryFlowHealthy` condition has status **BufferFillingUp**.
**Cause**: The backend export rate is too low compared to the log collection rate.
**Solution**:
- Option 1: Increase maximum backend ingestion rate. For example, by scaling out the SAP Cloud Logging instances.
- Option 2: Reduce emitted logs by re-configuring the LogPipeline (for example, by applying namespace or container filters).
- Option 3: Reduce emitted logs in your applications (for example, by changing severity level).