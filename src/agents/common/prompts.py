KYMA_DOMAIN_KNOWLEDGE = """
Kyma is an open-source project built upon the foundation of Kubernetes, designed to streamline the development and operation of enterprise-grade cloud-native applications. It provides a curated set of modular building blocks, encompassing the necessary capabilities for constructing and running sophisticated cloud applications while also offering a clear pathway to integrate with the SAP ecosystem.

## Kyma Components/Modules:
### API Gateway
  *Resources*: ApiGateway, ApiRule
### Istio
  *Resources*: Istio, VirtualService, Gateway, DestinationRule, PeerAuthentication
### SAP BTP Operator
  *Resources*: BtpOperator, ServiceInstance, ServiceBinding
### Application Connector
  *Resources*: Application, ApplicationConnector, CompassConnection
### Cloud Manager
  *Resources*: CloudManager, IpRange, AwsNfsVolume, AwsNfsVolumeBackup, AwsNfsBackupSchedule, AwsNfsVolumeRestore, GcpNfsVolume, GcpNfsVolumeBackup, GcpNfsBackupSchedule, GcpNfsVolumeRestore, AwsVpcPeering, GcpVpcPeering, AzureVpcPeering, AwsRedisInstance, GcpRedisInstance, AzureRedisInstance
### Docker Registry
  *Resources*: DockerRegistry
### Eventing
  *Resources*: Eventing, Subscription
### Keda
  *Resources*: Keda, ScaledObject, ScaledJob, TriggerAuthentication, ClusterTriggerAuthentication
### NATS
  *Resources*: NATS
### Serverless
  *Resources*: Serverless, Function
### Telemetry
  *Resources*: Telemetry, LogPipeline, LogParser, TracePipeline, MetricPipeline

## Kyma terminologies:
  *Terminologies*: Kyma, Module, Kyma Dashboard, Kyma CLI, Ory Oathkeeper, Envoy Proxy, CloudEvents, OpenTelemetry (OTLP), Fluent Bit, OpenTelemetry Collector, Service Instance, Service Binding, APIRule, Function, Subscription, LogPipeline, LogParser, TracePipeline, MetricPipeline, ServiceMapping, ScaledObject / ScaledJob (KEDA), Application (Compass context), Compass Runtime Agent, BTP Manager, Application Connector Manager, Eventing Manager, Keda Manager, NATS Manager, Serverless Operator, Telemetry Manager, Istio Operator, API Gateway Operator, Connectivity Proxy Operator, SAP BTP (Business Technology Platform), SAP Event Mesh (BEB), SAP Cloud Connector
"""

TOOL_CALLING_ERROR_HANDLING = """
## Failure Response Strategy

When a tool call fails, follow this protocol:

- ANALYZE THE FAILURE : Determine the type and likely cause of failure
- EVALUATE ALTERNATIVES : Consider if a different tool or approach might work , Check for missing or malformed parameters.
- INFORM THE USER : Acknowledge the user about the failure.

## Retry Logic :
Only retry if:

- If no specific error returned by tool
- You can modify the approach meaningfully (different parameters)
- You haven't already attempted this tool for the same request
- Maximum of THREE retry attempt per tool
"""


CHUNK_SUMMARIZER_PROMPT = """
            "Focusing on the query: '{query}'\n\n"
            "Summarize this text, extracting key points relevant to the query:\n"
            "{tool_response_chunk}\n\n"
            "Summary (keep it concise, no preamble):"
        """
