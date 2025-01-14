# Integrate With Dynatrace - Telemetry Module Setup - Ingest Traces
To start ingesting custom spans and Istio spans, you must enable the Istio tracing feature and then deploy a TracePipeline.
1. Deploy the Istio Telemetry resource:
```bash
kubectl apply -n istio-system -f - <<EOF
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
name: tracing-default
spec:
tracing:
- providers:
- name: "kyma-traces"
randomSamplingPercentage: 1.0
EOF
```
The default configuration has the **randomSamplingPercentage** property set to `1.0`, meaning it samples 1% of all requests. To change the sampling rate, adjust the property to the desired value, up to 100 percent.
> [!WARNING]
> Be cautious when you configure the **randomSamplingPercentage**:
> - Could cause high volume of traces.
> - The Kyma trace gateway component does not scale automatically.
1. Deploy the TracePipeline:
```bash
cat <<EOF | kubectl apply -f -
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: TracePipeline
metadata:
name: dynatrace
spec:
output:
otlp:
endpoint:
valueFrom:
secretKeyRef:
name: dynakube
namespace: ${DYNATRACE_NS}
key: apiurl
path: v2/otlp/v1/traces
headers:
- name: Authorization
prefix: Api-Token
valueFrom:
secretKeyRef:
name: dynakube
namespace: ${DYNATRACE_NS}
key: dataIngestToken
protocol: http
EOF
```
1. To find traces from your Kyma cluster in the Dynatrace UI, go to **Applications & Microservices** > **Distributed traces**.