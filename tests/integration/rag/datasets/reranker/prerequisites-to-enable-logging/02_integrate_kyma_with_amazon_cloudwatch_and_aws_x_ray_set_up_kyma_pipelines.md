# Integrate Kyma with Amazon CloudWatch and AWS X-Ray - Set Up Kyma Pipelines
Use the Kyma Telemetry module to enable ingestion of the signals from your workloads:
1. Deploy a LogPipeline:
> [!NOTE]
> The retention of of the CloudWatch Logs is set to 7 days. You can change that to fit your needs by adjusting the `log_retention_days` value.
```bash
kubectl apply -f - <<EOF
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: LogPipeline
metadata:
name: aws-cloudwatch
spec:
output:
custom: |
Name cloudwatch_logs
region \${AWS_REGION}
auto_create_group On
log_group_template /logs/\$cluster_identifier
log_group_name /logs/kyma-cluster
log_stream_template \$kubernetes['namespace_name'].\$kubernetes['pod_name'].\$kubernetes['container_name']
log_stream_name from-kyma-cluster
log_retention_days 7
variables:
- name: AWS_ACCESS_KEY_ID
valueFrom:
secretKeyRef:
name: aws-credentials
namespace: $K8S_NAMESPACE
key: AWS_ACCESS_KEY_ID
- name: AWS_SECRET_ACCESS_KEY
valueFrom:
secretKeyRef:
name: aws-credentials
namespace: $K8S_NAMESPACE
key: AWS_SECRET_ACCESS_KEY
- name: AWS_REGION
valueFrom:
secretKeyRef:
name: aws-credentials
namespace: $K8S_NAMESPACE
key: AWS_REGION
EOF
```
2. Deploy a TracePipeline:
```bash
kubectl apply -f - <<EOF
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: TracePipeline
metadata:
name: aws-xray
spec:
output:
otlp:
endpoint:
value: http://otel-collector.$K8S_NAMESPACE.svc.cluster.local:4317
EOF
```
3. Deploy a MetricPipeline:
```bash
kubectl apply -f - <<EOF
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: MetricPipeline
metadata:
name: aws-cloudwatch
spec:
input:
runtime:
enabled: true
istio:
enabled: true
prometheus:
enabled: true
output:
otlp:
endpoint:
value: http://otel-collector.$K8S_NAMESPACE.svc.cluster.local:4317
EOF
```