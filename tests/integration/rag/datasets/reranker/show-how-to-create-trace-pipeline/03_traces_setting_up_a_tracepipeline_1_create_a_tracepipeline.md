# Traces - Setting up a TracePipeline - 1. Create a TracePipeline
To ship traces to a new OTLP output, create a resource of the kind `TracePipeline` and save the file (named, for example, `tracepipeline.yaml`).
This configures the underlying OTel Collector with a pipeline for traces. It defines that the receiver of the pipeline is of the OTLP type and is accessible with the `telemetry-otlp-traces` service.
The default protocol is GRPC, but you can choose HTTP instead. Depending on the configured protocol, an `otlp` or an `otlphttp` exporter is used.  Ensure that the correct port is configured as part of the endpoint. Typically, port `4317` is used for GRPC and port `4318` for HTTP.
- For GRPC, use:
```yaml
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: TracePipeline
metadata:
name: backend
spec:
output:
otlp:
endpoint:
value: https://backend.example.com:4317
```
- For HTTP, use the `protocol` attribute:
```yaml
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: TracePipeline
metadata:
name: backend
spec:
output:
otlp:
protocol: http
endpoint:
value: https://backend.example.com:4318
```