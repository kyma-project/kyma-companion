# Integrate with SAP Cloud Logging - Ship Logs to SAP Cloud Logging
You can set up shipment of applications and access logs to SAP Cloud Logging. The following instructions distinguish application logs and access logs, which can be configured independently.
### Set Up Application Logs
<!-- using HTML so it's collapsed in GitHub, don't switch to docsify tabs -->
1. Deploy the LogPipeline for application logs with the following script:
<div tabs name="applicationlogs">
<details><summary>Script: Application Logs</summary>
```bash
kubectl apply -n sap-cloud-logging-integration -f - <<EOF
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: LogPipeline
metadata:
name: sap-cloud-logging-application-logs
spec:
input:
application:
containers:
exclude:
- istio-proxy
output:
http:
dedot: true
host:
valueFrom:
secretKeyRef:
name: sap-cloud-logging
namespace: sap-cloud-logging-integration
key: ingest-mtls-endpoint
tls:
cert:
valueFrom:
secretKeyRef:
name: sap-cloud-logging
namespace: sap-cloud-logging-integration
key: ingest-mtls-cert
key:
valueFrom:
secretKeyRef:
name: sap-cloud-logging
namespace: sap-cloud-logging-integration
key: ingest-mtls-key
uri: /customindex/kyma
EOF
```
</details>
</div>
2. Wait for the LogPipeline to be in the `Running` state. To check the state, run: `kubectl get logpipelines`.
### Set Up Access Logs
By default, Istio sidecar injection and Istio access logs are disabled in Kyma. To analyze access logs of your workload in the default SAP Cloud Logging dashboards shipped for SAP BTP, Kyma runtime, you must enable them:
1. Enable Istio sidecar injection for your workload. See [Enabling Istio Sidecar Injection](https://kyma-project.io/#/istio/user/tutorials/01-40-enable-sidecar-injection).
2. Enable Istio access logs for your workload. See [Configure Istio Access Logs](https://kyma-project.io/#/istio/user/tutorials/01-45-enable-istio-access-logs).
3. Deploy the LogPipeline for Istio access logs and enable access logs in Kyma with the following script:
<div tabs name="accesslogs">
<details><summary>Script: Access Logs</summary>
```bash
kubectl apply -n sap-cloud-logging-integration -f - <<EOF
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: LogPipeline
metadata:
name: sap-cloud-logging-access-logs
spec:
input:
application:
containers:
include:
- istio-proxy
output:
http:
dedot: true
host:
valueFrom:
secretKeyRef:
name: sap-cloud-logging
namespace: sap-cloud-logging-integration
key: ingest-mtls-endpoint
tls:
cert:
valueFrom:
secretKeyRef:
name: sap-cloud-logging
namespace: sap-cloud-logging-integration
key: ingest-mtls-cert
key:
valueFrom:
secretKeyRef:
name: sap-cloud-logging
namespace: sap-cloud-logging-integration
key: ingest-mtls-key
uri: /customindex/istio-envoy-kyma
EOF
```
</details>
</div>
4. Wait for the LogPipeline to be in the `Running` state. To check the state, run: `kubectl get logpipelines`.