# Traces - Overview
Observability tools aim to show the big picture, no matter if you're monitoring just a few or many components. In a cloud-native microservice architecture, a user request often flows through dozens of different microservices. Logging and monitoring tools help to track the request's path. However, they treat each component or microservice in isolation. This individual treatment results in operational issues.
[Distributed tracing](https://opentelemetry.io/docs/concepts/observability-primer/#understanding-distributed-tracing) charts out the transactions in cloud-native systems, helping you to understand the application behavior and relations between the frontend actions and backend implementation.
The following diagram shows how distributed tracing helps to track the request path:
![Distributed tracing](./assets/traces-intro.drawio.svg)
The Telemetry module provides a trace gateway for the shipment of traces of any container running in the Kyma runtime.
You can configure the trace gateway with external systems using runtime configuration with a dedicated Kubernetes API ([CRD](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/#customresourcedefinitions)) named TracePipeline.
The Trace feature is optional. If you don't want to use it, simply don't set up a TracePipeline.