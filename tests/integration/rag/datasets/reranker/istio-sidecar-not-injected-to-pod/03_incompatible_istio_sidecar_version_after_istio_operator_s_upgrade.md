# Incompatible Istio Sidecar Version After Istio Operator's Upgrade

<!-- open-source-only -->
# Incompatible Istio Sidecar Version After Istio Operator's Upgrade

## Symptom

You upgraded the Istio module, and mesh connectivity is broken.

## Cause

The sidecar version in Pods must match the installed Istio version to ensure proper mesh connectivity. During an upgrade of the Istio module to a new version Istio Operator's `ProxySidecarReconcilation` component performs a rollout for most common workload types ensuring that the injected Istio sidecar proxies are updated correctly.
However, if a resource is a Job, a ReplicaSet that is not managed by any Deployment, or a Pod that is not managed by any other resource, the restart cannot be performed automatically.

You must manually restart such user-defined workloads to ensure proper functionality with the updated Istio version.

## Solution

To learn if any Pods or workloads require a manual restart, follow these steps:

1. Check the installed Istio version. From the `istiod` deployment in a running cluster, run:

   ```bash
   export PILOT_ISTIO_VERSION=$(kubectl get deployment istiod -n istio-system -o json | jq '.spec.template.spec.containers | .[].image' | sed 's/[^:"]*[:]//' | sed 's/["]//g')
   ```

2. Get the list of objects which require rollout. Find all Pods with outdated sidecars. The returned list follows the `name/namespace` format. The empty output means that there is no Pod that requires migration. To find all outdated Pods, run:

   ```bash
   COMMON_ISTIO_PROXY_IMAGE_PREFIX="europe-docker.pkg.dev/kyma-project/prod/external/istio/proxyv2"
   kubectl get pods -A -o json | jq -rc '.items | .[] | select(.spec.containers[].image | startswith("'"${COMMON_ISTIO_PROXY_IMAGE_PREFIX}"'") and (endswith("'"${PILOT_ISTIO_VERSION}"'") | not))  | "\(.metadata.name)/\(.metadata.namespace)"'
   ```

3. After you find a set of objects that require the manual update, restart their related workloads so that new Istio sidecars are injected into the Pods.
