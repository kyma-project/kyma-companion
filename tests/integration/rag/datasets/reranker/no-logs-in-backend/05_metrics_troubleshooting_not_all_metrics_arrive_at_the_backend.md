# Metrics - Troubleshooting - Not All Metrics Arrive at the Backend
**Symptom**:
- The backend is reachable and the connection is properly configured, but some metrics are refused.
- In the MetricPipeline status, the `TelemetryFlowHealthy` condition has status **SomeDataDropped**.
**Cause**: It can happen due to a variety of reasons - for example, the backend is limiting the ingestion rate.
**Solution**:
1. Check the `telemetry-metric-gateway` Pods for error logs by calling `kubectl logs -n kyma-system {POD_NAME}`. Also, check your observability backend to investigate potential causes.
2. If backend is limiting the rate by refusing metrics, try the options desribed in [Gateway Buffer Filling Up](#gateway-buffer-filling-up).
3. Otherwise, take the actions appropriate to the cause indicated in the logs.