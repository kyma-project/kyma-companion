# Istio Sidecar Proxy Injection Issues - Cause
By default, the Istio module does not automatically inject an Istio sidecar proxy into any Pods you create. To inject a Pod with an Istio sidecar proxy, you must explicitly enable injection for the Pod's Deployment or for the entire namespace. If you have done this and the sidecar is still not installed, follow the remedy steps to identify which settings are preventing the injection.
A Pod is not injected with an Istio sidecar proxy if:
- Istio sidecar proxy injection is disabled at the namespace level
- The **sidecar.istio.io/inject** label on the Pod is set to `false`
- The Pod's `spec` contains `hostNetwork: true`