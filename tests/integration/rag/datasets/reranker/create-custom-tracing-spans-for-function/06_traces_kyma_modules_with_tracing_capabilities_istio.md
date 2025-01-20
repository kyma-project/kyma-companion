# Traces - Kyma Modules With Tracing Capabilities - Istio
The Istio module is crucial in distributed tracing because it provides the [ingress gateway](https://istio.io/latest/docs/tasks/traffic-management/ingress/ingress-control/). Typically, this is where external requests enter the cluster scope and are enriched with trace context if it hasn’t happened earlier. Furthermore, every component that’s part of the Istio Service Mesh runs an Istio proxy, which propagates the context properly but also creates span data. If Istio tracing is activated and taking care of trace propagation in your application, you get a complete picture of a trace, because every component automatically contributes span data. Also, Istio tracing is pre-configured to be based on the vendor-neutral [W3C Trace Context](https://www.w3.org/TR/trace-context/) protocol.
The Istio module is configured with an [extension provider](https://istio.io/latest/docs/tasks/observability/telemetry/) called `kyma-traces`. To activate the provider on the global mesh level using the Istio [Telemetry API](https://istio.io/latest/docs/reference/config/telemetry/#Tracing), place a resource to the `istio-system` namespace. The following code samples help setting up the Istio tracing feature:
<!-- tabs:start -->
#### **Extension Provider**
The following example configures all Istio proxies with the `kyma-traces` extension provider, which, by default, reports span data to the trace gateway of the Telemetry module.
```yaml
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
name: tracing-default
namespace: istio-system
spec:
tracing:
- providers:
- name: "kyma-traces"
```
#### **Sampling Rate**
By default, the sampling rate is configured to 1%. That means that only 1 trace out of 100 traces is reported to the trace gateway, and all others are dropped. The sampling decision itself is propagated as part of the [trace context](https://www.w3.org/TR/trace-context/#sampled-flag) so that either all involved components are reporting the span data of a trace, or none.
> [!TIP]
> If you increase the sampling rate, you send more data your tracing backend and cause much higher network utilization in the cluster.
> To reduce costs and performance impacts in a production setup, a very low percentage of around 5% is recommended.
To configure an "always-on" sampling, set the sampling rate to 100%:
```yaml
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
name: tracing-default
namespace: istio-system
spec:
tracing:
- providers:
- name: "kyma-traces"
randomSamplingPercentage: 100.00
```
#### **Namespaces or Workloads**
If you need specific settings for individual namespaces or workloads, place additional Telemetry resources. If you don't want to report spans at all for a specific workload, activate the `disableSpanReporting` flag with the selector expression.
```yaml
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
name: tracing-default
namespace: my-namespace
spec:
selector:
matchLabels:
kubernetes.io/name: "my-app"
tracing:
- providers:
- name: "kyma-traces"
randomSamplingPercentage: 100.00
```
#### **Trace Context Without Spans**
To enable the propagation of the [W3C Trace Context](https://www.w3.org/TR/trace-context/) only, without reporting any spans (so the actual tracing feature is disabled), you must enable the `kyma-traces` provider with a sampling rate of 0. With this configuration, you get the relevant trace context into the [access logs](https://kyma-project.io/#/istio/user/tutorials/01-45-enable-istio-access-logs) without any active trace reporting.
```yaml
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
name: tracing-default
namespace: istio-system
spec:
tracing:
- providers:
- name: "kyma-traces"
randomSamplingPercentage: 0
```
<!-- tabs:end -->