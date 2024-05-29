# Istio Service Mesh

A service mesh is an infrastructure layer that handles service-to-service communication, proxying, service discovery, traceability, and security, independently of the code of the services. To deliver this functionality, Kyma uses the [Istio](https://istio.io/docs/concepts/what-is-istio/) service mesh that is customized for the specific needs of the implementation.

The main principle of the Istio service mesh is to inject Pods of every service with the Envoy sidecar proxy. Envoy intercepts the communication between the services and regulates it by applying and enforcing the rules you create.

By default, Istio installed by Kyma Istio Operator has [mutual TLS (mTLS)](https://istio.io/docs/concepts/security/#mutual-tls-authentication) disabled. See how to [enable sidecar proxy injection](./operation-guides/02-20-enable-sidecar-injection.md). You can manage mTLS traffic in services or at a namespace level by creating [DestinationRules](https://istio.io/docs/reference/config/networking/destination-rule/) and [Peer Authentications](https://istio.io/docs/tasks/security/authentication/authn-policy/). If you disable sidecar injection for a service or for a namespace, you must manage their traffic configuration by creating appropriate DestinationRules and Peer Authentications.

> [!NOTE]
>For security and performance, we use the [distroless](https://istio.io/docs/ops/configuration/security/harden-docker-images/) version of Istio images. Those images are not Debian-based and are slimmed down to reduce any potential attack surface and increase startup time.
