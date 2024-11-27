Istio sidecar proxy injection can be enabled in two ways:

## Prerequisites
- Istio module must be added
- kubectl installed (for CLI method) or access to Kyma dashboard

## Namespace-Level Injection
**Using Kyma Dashboard:**
1. Select target namespace
2. Click Edit
3. Enable Istio sidecar proxy injection toggle in UI Form
4. Save changes

**Using kubectl:**
```bash
kubectl label namespace {YOUR_NAMESPACE} istio-injection=enabled
```

## Deployment-Level Injection
**Using Kyma Dashboard:**
1. Select namespace
2. Go to Workloads > Deployments
3. Select target Deployment
4. Click Edit
5. Enable Istio sidecar proxy injection toggle in UI Form
6. Save changes

**Using kubectl:**
```bash
kubectl patch -n {YOUR_NAMESPACE} deployments/{YOUR_DEPLOYMENT} -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"true"}}}}}'
```

## Known Limitations
The sidecar proxy will not be injected if:
- Namespace-level injection is disabled
- Pod has `sidecar.istio.io/inject: false` label
- Pod spec includes `hostNetwork: true`

## Results
- For namespace: All new Pods in the namespace will get the sidecar proxy
- For deployment: All Pods in the deployment get instantly injected with the sidecar proxy