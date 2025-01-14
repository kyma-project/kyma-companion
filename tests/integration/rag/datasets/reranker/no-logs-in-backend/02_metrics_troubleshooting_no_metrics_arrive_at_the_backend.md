# Metrics - Troubleshooting - No Metrics Arrive at the Backend
### No Metrics Arrive at the Backend
**Symptom**:
- No metrics arrive at the backend.
- In the MetricPipeline status, the `TelemetryFlowHealthy` condition has status **AllDataDropped**.
**Cause**: Incorrect backend endpoint configuration (such as using the wrong authentication credentials) or the backend is unreachable.
**Solution**:
1. Check the `telemetry-metric-gateway` Pods for error logs by calling `kubectl logs -n kyma-system {POD_NAME}`.
2. Check if the backend is up and reachable.
3. Fix the errors.