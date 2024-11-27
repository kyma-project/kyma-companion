### Problem
Istio sidecar proxy is not injected into a Pod.

### Causes of Failed Sidecar Injection

A Pod will not receive an Istio sidecar proxy injection under these conditions:
- The namespace has Istio sidecar proxy injection disabled
- The Pod has the `sidecar.istio.io/inject` label explicitly set to `false`
- The Pod specification includes `hostNetwork: true`

### Solutions

**Namespace-Level Injection**
- Using Kyma Dashboard:
  1. Navigate to the target namespace
  2. Click "Edit"
  3. Enable Istio sidecar proxy injection using the toggle in UI Form
  4. Save changes

- Using kubectl:
```bash
kubectl label namespace {YOUR_NAMESPACE} istio-injection=enabled
```

**Deployment-Level Injection**
- Using Kyma Dashboard:
  1. Navigate to the target namespace
  2. Go to Workloads > Deployments
  3. Select the deployment
  4. Click "Edit"
  5. Enable Istio sidecar proxy injection using the toggle in UI Form
  6. Save changes

- Using kubectl:
```bash
kubectl patch -n {YOUR_NAMESPACE} deployments/{YOUR_DEPLOYMENT} -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"true"}}}}}'
```

**Prerequisites**
- Istio module must be added to your Kyma installation
- kubectl must be installed for CLI operations (optional if using Kyma dashboard)

After applying either solution, the affected resources will be labeled with `istio-injection: enabled`. For namespace-level injection, all new Pods in the namespace will receive the sidecar proxy. For deployment-level injection, all Pods in the deployment will be immediately injected with the Istio sidecar proxy.