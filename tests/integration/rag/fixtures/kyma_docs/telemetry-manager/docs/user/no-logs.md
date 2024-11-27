### No Logs Arrive at the Backend

**Symptom**:

- No logs arrive at the backend.
- In the LogPipeline status, the `TelemetryFlowHealthy` condition has status **AllDataDropped**.

**Cause**: Incorrect backend endpoint configuration (for example, using the wrong authentication credentials) or the backend being unreachable.

**Remedy**:

- Check the `telemetry-fluent-bit` Pods for error logs by calling `kubectl logs -n kyma-system {POD_NAME}`.
- Check if the backend is up and reachable.