# Istio Sidecar Injection Troubleshooting

This guide helps you diagnose and resolve common issues with Istio sidecar injection in Kyma.

## Overview

Istio uses a mutating admission webhook to inject sidecar proxies into Pods. When injection fails or behaves unexpectedly, use the steps in this guide to identify the root cause.

## Prerequisites

- `kubectl` configured to access your Kyma cluster
- Kyma Istio module installed

## Common Issues

### Sidecar Not Injected

If your Pod does not have the Istio sidecar container (`istio-proxy`), check the following.

#### Verify Namespace Label

Istio injection is enabled per namespace via the `istio-injection: enabled` label. To check whether the label is set:

```bash
kubectl get namespace <your-namespace> --show-labels
```

If the label is missing, enable injection:

```bash
kubectl label namespace <your-namespace> istio-injection=enabled
```

#### Check Pod Annotations

A Pod-level annotation can opt out of injection even when the namespace label is set:

```yaml
metadata:
  annotations:
    sidecar.istio.io/inject: "false"
```

Remove or set the annotation to `"true"` to re-enable injection.

#### Inspect the Mutating Webhook Configuration

```bash
kubectl get mutatingwebhookconfigurations istio-sidecar-injector -o yaml
```

Ensure the webhook `namespaceSelector` and `objectSelector` rules match your namespace and Pod.

### Sidecar Crashes at Startup

If `istio-proxy` starts but immediately enters `CrashLoopBackOff`, inspect the container logs:

```bash
kubectl logs <pod-name> -c istio-proxy -n <namespace>
```

Common causes:

- The Envoy configuration references a cluster or route that does not exist yet.
- Certificate rotation failed; check the Istiod logs:

```bash
kubectl logs -n istio-system deployment/istiod
```

### mTLS Policy Conflicts

When a `PeerAuthentication` policy requires `STRICT` mTLS but a client sends plain-text traffic, connections are refused with a 503 error.

#### Diagnose with istioctl

```bash
istioctl analyze -n <namespace>
```

#### Fix the Policy

Either relax the policy to `PERMISSIVE` or ensure all clients are enrolled in the mesh:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: <namespace>
spec:
  mtls:
    mode: PERMISSIVE
```

## Checking Istio Module Status

To verify the Kyma Istio module is healthy:

```bash
kubectl get istio -n kyma-system
```

Expected output:

```
NAME      STATE   AGE
default   Ready   5d
```

If the state is not `Ready`, describe the resource for events:

```bash
kubectl describe istio default -n kyma-system
```

## Related Resources

- [Istio Module Overview](./01-istio-overview.md)
- [Configure mTLS](./02-configure-mtls.md)
- [Peer Authentication Reference](./resources/peer-authentication.md)
