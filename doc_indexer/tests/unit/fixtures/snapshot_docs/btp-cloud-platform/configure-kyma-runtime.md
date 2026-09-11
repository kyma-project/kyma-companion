<!-- loio a91c6810ccf34cd0800b4a8bdf0e85b8 -->

# Configure Kyma Runtime

Learn how to configure your SAP BTP Kyma runtime, including scaling, networking, and access settings.

<!-- loio -->

## Overview

After provisioning a Kyma runtime on SAP BTP, you can customize its configuration through the SAP BTP cockpit or the btp CLI. This guide covers the most frequently needed configuration tasks.

<!-- loio 7a90e80826fd4a24b89f74f8e3ec52d8 -->

## Prerequisites

- An SAP BTP global account with the Kyma runtime entitlement.
- **Account Administrator** or **Subaccount Administrator** role.
- The btp CLI installed and authenticated.

<!-- loio -->

## Scale the Kyma Runtime

Kyma runtime auto-scales based on workload, but you can set minimum and maximum node counts per node pool.

### View Current Node Pools

Navigate to your subaccount in the SAP BTP cockpit, then choose **Kyma Environment** > **Node Pools** to view the configured pools and their current sizes.

### Modify Node Counts via btp CLI

```bash
btp update services/instance \
  --name <kyma-instance-name> \
  --subaccount <subaccount-id> \
  --parameters '{
    "autoscalerMin": 3,
    "autoscalerMax": 10
  }'
```

Replace `<kyma-instance-name>` and `<subaccount-id>` with your values.

<!-- loio 4c8d3e1a2b7f4e9c8d3e1a2b7f4e9c8d -->

## Configure Custom Domains

By default, Kyma exposes services under `*.kyma.ondemand.com`. To use a custom domain:

### Step 1 -- Add a Custom Domain in the BTP Cockpit

1. Open your subaccount and choose **Kyma Environment**.
2. Under **Custom Domains**, choose **Add**.
3. Enter your domain and upload the TLS certificate and key.

### Step 2 -- Create a DNS Entry

Point your custom domain to the Kyma Ingress Gateway's external IP:

```bash
kubectl get svc -n istio-system istio-ingressgateway \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Create an `A` record in your DNS provider pointing `*.your-domain.com` to that IP.

### Step 3 -- Reference the Custom Domain in APIRule

Update your `APIRule` to use the custom host:

```yaml
spec:
  hosts:
    - my-service.your-domain.com
  gateway: kyma-system/kyma-gateway
```

<!-- loio -->

## Configure Network Policies

By default, all Pods in the Kyma cluster can communicate with each other. To restrict traffic:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: my-namespace
spec:
  podSelector: {}
  policyTypes:
    - Ingress
```

Apply this policy to deny all inbound traffic within a namespace, then add explicit allow rules for the services that need to communicate.

<!-- loio 9e1f5b2a3c6d4e7f8a0b1c2d3e4f5a6b -->

## Manage Kyma Module Configuration

Kyma modules are installed as separate operators. You can configure them via the `Kyma` custom resource:

```bash
kubectl edit kyma default -n kyma-system
```

Under `.spec.modules`, add or modify module entries:

```yaml
spec:
  modules:
    - name: istio
      channel: regular
    - name: api-gateway
      channel: regular
    - name: serverless
      channel: fast
```

### Available Channels

| Channel | Description |
|---|---|
| `regular` | Stable releases, updated on the standard cadence. |
| `fast` | Latest releases; may include features not yet in `regular`. |

<!-- loio -->

## Related Information

- [Kyma Runtime Overview](kyma-runtime-overview.md)
- [Manage Entitlements](manage-entitlements.md)
- [btp CLI Reference](btp-cli-reference.md)
