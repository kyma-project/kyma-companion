# TracePipeline - Sample Custom Resource
The following TracePipeline object defines a pipeline that integrates into the local Jaeger instance:
```yaml
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: TracePipeline
metadata:
name: jaeger
generation: 1
spec:
output:
otlp:
endpoint:
value: http://jaeger-collector.jaeger.svc.cluster.local:4317
status:
conditions:
- lastTransitionTime: "2024-02-29T01:18:28Z"
message: Trace gateway Deployment is ready
observedGeneration: 1
reason: GatewayReady
status: "True"
type: GatewayHealthy
- lastTransitionTime: "2024-02-29T01:18:27Z"
message: ""
observedGeneration: 1
reason: ConfigurationGenerated
status: "True"
type: ConfigurationGenerated
```
For further examples, see the [samples](https://github.com/kyma-project/telemetry-manager/tree/main/config/samples) directory.