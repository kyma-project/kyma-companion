# Application Logs - Architecture
In the Kyma cluster, the Telemetry module provides a DaemonSet of [Fluent Bit](https://fluentbit.io/) acting as a agent. The agent tails container logs from the Kubernetes container runtime and ships them to a backend.
![Architecture](./assets/logs-arch.drawio.svg)
1. Container logs are stored by the Kubernetes container runtime under the `var/log` directory and its subdirectories.
2. Fluent Bit runs as a [DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/) (one instance per Node), detects any new log files in the folder, and tails them using a filesystem buffer for reliability.
3. Fluent Bit discovers additional Pod metadata, such as Pod annotations and labels.
4. Telemetry Manager configures Fluent Bit with your output configuration, observes the log flow, and reports problems in the LogPipeline status.
5. The log agent sends the data to the observability system that's specified in your `LogPipeline` resource - either within the Kyma cluster, or, if authentication is set up, to an external observability backend. You can use the integration with HTTP to integrate a system directly or with an additional Fluentd installation.
6. To analyze and visualize your logs, access the internal or external observability system.
### Telemetry Manager
The LogPipeline resource is watched by Telemetry Manager, which is responsible for generating the custom parts of the Fluent Bit configuration.
![Manager resources](./assets/logs-resources.drawio.svg)
1. Telemetry Manager watches all LogPipeline resources and related Secrets.
2. Furthermore, Telemetry Manager takes care of the full lifecycle of the Fluent Bit DaemonSet itself. Only if you defined a LogPipeline, the agent is deployed.
3. Whenever the configuration changes, Telemetry Manager validates the configuration (with a [validating webhook](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)) and generates a new configuration for the Fluent Bit DaemonSet, where several ConfigMaps for the different aspects of the configuration are generated.
4. Referenced Secrets are copied into one Secret that is also mounted to the DaemonSet.
### Log Agent
If a LogPipeline is defined, a DaemonSet is deployed acting as an agent. The agent is based on [Fluent Bit](https://fluentbit.io/) and encompasses the collection of application logs provided by the Kubernetes container runtime. The agent sends all data to the configured backend.
### Pipelines
<!--- Pipelines is not part of Help Portal docs --->
Fluent Bit comes with a pipeline concept, which supports a flexible combination of inputs with outputs and filtering in between. For details, see [Fluent Bit: Output](https://docs.fluentbit.io/manual/concepts/data-pipeline/output).
Kyma's Telemetry module brings a predefined setup of the Fluent Bit DaemonSet and a base configuration, which assures that the application logs of the workloads in the cluster are processed reliably and efficiently. Additionally, the Telemetry module provides a Kubernetes API called `LogPipeline` to configure outputs with some filtering capabilities.
This approach ensures reliable buffer management and isolation of pipelines, while keeping flexibility on customizations.
![Pipeline Concept](./assets/logs-pipelines.drawio.svg)
1. A dedicated `tail` **input** plugin reads the application logs, which are selected in the input section of the `LogPipeline`. Each `tail` input uses a dedicated `tag` with the name `<logpipeline>.*`.
2. The application logs are enriched by the `kubernetes` **filter**. You can add your own filters to the default filters.
3. Based on the default and custom filters, you get the desired **output** for each `LogPipeline`.
This approach assures a reliable buffer management and isolation of pipelines, while keeping flexibility on customizations.