# Integrate with SAP Cloud Logging - Prerequisites
- Kyma as the target deployment environment.
- The [Telemetry module](../../README.md) is added. For details, see [Quick Install](https://kyma-project.io/#/02-get-started/01-quick-install). <!-- This link differs for OS and SKR -->
- If you want to use Istio access logs, make sure that the [Istio module](https://kyma-project.io/#/istio/user/README) is added.
- An instance of [SAP Cloud Logging](https://help.sap.com/docs/cloud-logging?locale=en-US&version=Cloud) with OpenTelemetry enabled to ingest distributed traces.
> [!TIP]
> Create the instance with the SAP BTP service operator (see [Create an SAP Cloud Logging Instance through SAP BTP Service Operator](https://help.sap.com/docs/cloud-logging/cloud-logging/create-sap-cloud-logging-instance-through-sap-btp-service-operator?locale=en-US&version=Cloud)), because it takes care of creation and rotation of the required Secret. However, you can choose any other method of creating the instance and the Secret, as long as the parameter for OTLP ingestion is enabled in the instance. For details, see [Configuration Parameters](https://help.sap.com/docs/cloud-logging/cloud-logging/configuration-parameters?locale=en-US&version=Cloud).
- A Secret in the respective namespace in the Kyma cluster, holding the credentials and endpoints for the instance. In the following example, the Secret is named `sap-cloud-logging` and the namespace `sap-cloud-logging-integration`, as illustrated in the [secret-example.yaml](https://github.com/kyma-project/telemetry-manager/blob/main/docs/user/integration/sap-cloud-logging/secret-example.yaml).
<!-- markdown-link-check-disable -->
- Kubernetes CLI (kubectl) (see [Install the Kubernetes Command Line Tool](https://developers.sap.com/tutorials/cp-kyma-download-cli.html)).
<!-- markdown-link-check-enable -->
- UNIX shell or Windows Subsystem for Linux (WSL) to execute commands.