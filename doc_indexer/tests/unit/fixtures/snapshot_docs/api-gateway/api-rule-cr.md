# APIRule Custom Resource

The `APIRule` custom resource (CR) lets you expose services within the Kyma cluster to the outside world or configure traffic policies for internal communication.

## Overview

`APIRule` is defined in the `gateway.kyma-project.io/v2` API group. It wraps Istio `VirtualService` and `AuthorizationPolicy` resources, giving you a single place to control routing and access.

## APIRule Spec

```yaml
apiVersion: gateway.kyma-project.io/v2
kind: APIRule
metadata:
  name: my-service
  namespace: default
spec:
  hosts:
    - my-service.example.com
  gateway: kyma-system/kyma-gateway
  rules:
    - path: /.*
      methods:
        - GET
        - POST
      noAuth: true
      service:
        name: my-service
        port: 8080
```

### Spec Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `hosts` | `[]string` | Yes | Hostnames that the API rule applies to. |
| `gateway` | `string` | Yes | Namespace and name of the Istio `Gateway` resource, separated by `/`. |
| `rules` | `[]Rule` | Yes | List of routing rules. At least one is required. |
| `timeout` | `string` | No | Global request timeout. Defaults to `180s`. Overridden per rule. |

### Rule Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | URL path matcher. Supports regular expressions. |
| `methods` | `[]string` | Yes | Allowed HTTP methods. |
| `service` | `Service` | Yes | Target service name and port. |
| `noAuth` | `bool` | No | When `true`, no authentication is required. Mutually exclusive with `jwt`. |
| `jwt` | `JwtConfig` | No | JWT authentication configuration. |
| `timeout` | `string` | No | Per-rule timeout. Overrides the global timeout. |

## Authentication Modes

### No Authentication

Set `noAuth: true` to allow unauthenticated access:

```yaml
rules:
  - path: /public
    methods: [GET]
    noAuth: true
    service:
      name: my-service
      port: 8080
```

### JWT Authentication

Configure JWT validation to protect endpoints:

```yaml
rules:
  - path: /api/.*
    methods: [GET, POST, PUT, DELETE]
    jwt:
      authentications:
        - issuer: https://accounts.example.com
          jwksUri: https://accounts.example.com/.well-known/jwks.json
      authorizations:
        - requiredScopes:
            - read
            - write
    service:
      name: my-service
      port: 8080
```

## Status

After applying an `APIRule`, check its status:

```bash
kubectl get apirule my-service -n default -o yaml
```

The `.status` field reflects the reconciliation outcome:

```yaml
status:
  state: Ready
  description: ""
  conditions:
    - type: Ready
      status: "True"
      reason: ReconcileSucceeded
      message: ""
```

### Status States

| State | Description |
|---|---|
| `Ready` | The rule was applied successfully. The underlying `VirtualService` and `AuthorizationPolicy` are in sync. |
| `Processing` | The controller is currently reconciling the resource. |
| `Error` | Reconciliation failed. See `description` and `conditions` for details. |
| `Warning` | The rule was applied but with non-critical issues. For example, a deprecated field was used. |

## Troubleshooting

### APIRule Shows Error State

Check the controller logs:

```bash
kubectl logs -n kyma-system deployment/api-gateway-controller-manager
```

### 404 on Exposed Endpoint

Verify the underlying `VirtualService` was created:

```bash
kubectl get virtualservice -n default
```

### CORS Issues

Add a `corsPolicy` to the `APIRule` spec or configure it on the target service. APIRule does not automatically inject CORS headers.

## Related Resources

- [API Gateway Module Overview](./01-api-gateway-overview.md)
- [Expose a Service](../tutorials/01-10-expose-workload.md)
- [JWT Configuration Reference](./jwt-config.md)
