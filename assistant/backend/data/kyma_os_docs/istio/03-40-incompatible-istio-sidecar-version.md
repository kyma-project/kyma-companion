# Incompatible Istio Sidecar Version After Istio Operator's Upgrade

## Symptom

You upgraded Kyma Istio Operator, and mesh connectivity is broken.

## Cause

By default, Kyma Istio Operator has Istio sidecar injection disabled - it does not automatically inject the Istio sidecar into any Pod in a cluster.
The sidecar version in Pods must match the installed Istio version to ensure proper mesh connectivity. During an upgrade of Kyma Istio Operator to a new version, existing sidecars injected into Pods remain in the original version, potentially causing connectivity issues.

Kyma Istio Operator contains the `ProxySidecarReconcilation` component that performs a rollout for most common workload types like Deployments and DaemonSets. This component ensures that all running sidecars are updated correctly.
However, there are some user-defined workloads that can't be rolled out automatically. This includes standalone Pods without any management mechanism like a ReplicaSet or a Job.

You must manually restart such user-defined workloads to ensure proper functionality with the updated Istio version.

## Remedy

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
