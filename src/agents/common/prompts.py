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

K8S_DOMAIN_KNOWLEDGE = """
## Kubernetes Resources:
### Workloads
  *Resources*: Pod, Deployment, StatefulSet, DaemonSet, Job, CronJob, ReplicaSet, ReplicationController (older, generally replaced by ReplicaSet/Deployment)

### Service Discovery & Networking
  *Resources*: Service (ClusterIP, NodePort, LoadBalancer, ExternalName types), Ingress, EndpointSlice, Endpoints (older mechanism, still used), NetworkPolicy, GatewayClass , HTTPRoute (Gateway API), TCPRoute, GRPCRoute

### Config & Metadata
  *Resources*: ConfigMap, Secret, ResourceQuota, LimitRange, DownwardAPI (mechanism within Pod spec, not a standalone resource), Namespace

### Storage
  *Resources*: PersistentVolume (PV), PersistentVolumeClaim (PVC), StorageClass, Volume, VolumeAttachment, CSIDriver, CSINode, VolumeSnapshot, VolumeSnapshotClass

### RBAC & Identity
  *Resources*: ServiceAccount, Role, RoleBinding, ClusterRole, ClusterRoleBinding

### Cluster Architecture & Nodes
  *Resources*: Node, APIService (for API aggregation), ComponentStatus (Control Plane component health, status often read-only)

### Observability (Core & Common Add-ons)
  *Resources*: Metrics API (provided by Metrics Server, e.g., `metrics.k8s.io`), Event (also listed under Config & Metadata), Logs (accessed via API, often collected by tools like Fluentd), Kubernetes Dashboard (add-on), Prometheus Operator CRDs (common add-on), Tracing instrumentation (usually via sidecars/agents like OpenTelemetry) *[Note: Many observability components are add-ons/external tools integrated with Kubernetes APIs]*

### Autoscaling
  *Resources*: HorizontalPodAutoscaler (HPA), VerticalPodAutoscaler (VPA - often via CRDs), Cluster Autoscaler (component, not a direct API resource, interacts with Nodes/Cloud Provider)

### Security
  *Resources*: NetworkPolicy (also listed under Networking), Secret (also listed under Config), ServiceAccount (also listed under RBAC), PodSecurityPolicy (PSP - deprecated in v1.21, removed in v1.25), Pod Security Admission (PSA - built-in admission controller, configured via Namespace labels), CertificateSigningRequest (CSR)

### API Extensibility
  *Resources*: CustomResourceDefinition (CRD), Custom Resource (CR - instances defined by CRDs), AdmissionConfiguration (MutatingWebhookConfiguration, ValidatingWebhookConfiguration)

### Policy
  *Resources*: LimitRange (also under Config), ResourceQuota (also under Config), NetworkPolicy (also under Networking/Security), PodDisruptionBudget (PDB)
"""


TOOL_CALLING_ERROR_HANDLING = """
# ** Error Handling**
## Check conversation history : 
- If a tool call fails analyze the error and attempt to fix the issue:
- Check for missing or malformed parameters.
- Verify if the correct tool is assigned with correct name.
- If three consecutive tool calls request fail, do not attempt further tool calls. Instead, respond to the user with:
- A clear acknowledgment of the issue (e.g., "I encountered an error while retrieving the information.").
- A concise explanation (if helpful) without technical details.
"""
