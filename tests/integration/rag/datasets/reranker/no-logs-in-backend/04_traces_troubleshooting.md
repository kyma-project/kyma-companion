# Traces - Troubleshooting
### No Spans Arrive at the Backend
**Symptom**: In the TracePipeline status, the `TelemetryFlowHealthy` condition has status **AllDataDropped**.
**Cause**: Incorrect backend endpoint configuration (such as using the wrong authentication credentials), or the backend is unreachable.
**Solution**:
1. Check the `telemetry-trace-gateway` Pods for error logs by calling `kubectl logs -n kyma-system {POD_NAME}`.
2. Check if the backend is up and reachable.
3. Fix the errors.
### Not All Spans Arrive at the Backend
**Symptom**:
- The backend is reachable and the connection is properly configured, but some spans are refused.
- In the TracePipeline status, the `TelemetryFlowHealthy` condition has status **SomeDataDropped**.
**Cause**: It can happen due to a variety of reasons - for example, the backend is limiting the ingestion rate.
**Solution**:
1. Check the `telemetry-trace-gateway` Pods for error logs by calling `kubectl logs -n kyma-system {POD_NAME}`. Also, check your observability backend to investigate potential causes.
2. If the backend is limiting the rate by refusing spans, try the options desribed in [Gateway Buffer Filling Up](#gateway-buffer-filling-up).
3. Otherwise, take the actions appropriate to the cause indicated in the logs.
### Custom Spans Don’t Arrive at the Backend, but Istio Spans Do
**Cause**: Your SDK version is incompatible with the OTel Collector version.
**Solution**:
1. Check which SDK version you are using for instrumentation.
2. Investigate whether it is compatible with the OTel Collector version.
3. If required, upgrade to a supported SDK version.
### Trace Backend Shows Fewer Traces than Expected
**Cause**: By [default](#istio), only 1% of the requests are sent to the trace backend for trace recording.
**Solution**:
To see more traces in the trace backend, increase the percentage of requests by changing the default settings.
If you just want to see traces for one particular request, you can manually force sampling:
1. Create a `values.yaml` file.
The following example sets the value to `60`, which means 60% of the requests are sent to the tracing backend.
```yaml
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
name: kyma-traces
namespace: istio-system
spec:
tracing:
- providers:
- name: "kyma-traces"
randomSamplingPercentage: 60
```
2. To override the default percentage, change the value for the **randomSamplingPercentage** attribute.
3. Deploy the `values.yaml` to your existing Kyma installation.
### Gateway Buffer Filling Up
**Symptom**: In the TracePipeline status, the `TelemetryFlowHealthy` condition has status **BufferFillingUp**.
**Cause**: The backend export rate is too low compared to the gateway ingestion rate.
**Solution**:
- Option 1: Increase the maximum backend ingestion rate - for example, by scaling out the SAP Cloud Logging instances.
- Option 2: Reduce the emitted spans in your applications.
### Gateway Throttling
**Symptom**:
- In the TracePipeline status, the `TelemetryFlowHealthy` condition has status **GatewayThrottling**.
- Also, your application might have error logs indicating a refusal for sending traces to the gateway.
**Cause**: Gateway cannot receive spans at the given rate.
**Solution**: Manually scale out the gateway by increasing the number of replicas for the trace gateway. See [Module Configuration and Status](https://kyma-project.io/#/telemetry-manager/user/01-manager?id=module-configuration).