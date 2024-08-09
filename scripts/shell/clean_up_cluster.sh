#!/usr/bin/env bash

##############################################################################
# NOTE: This script is used in the GitHub Actions workflow.
# Make sure any changes are compatible with the existing workflows.
##############################################################################

# standard bash error handling
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

# Define namespaces to exclude from deletion
EXCLUDED_NAMESPACES=("default" "kube-system" "kube-public" "kube-node-lease")

# Define the maximum number of retries
MAX_RETRIES=5

# Generate a regex pattern for excluded namespaces
EXCLUDED_REGEX=$(IFS=\|; echo "${EXCLUDED_NAMESPACES[*]}")

# Function to check if a namespace is in the excluded list
is_excluded_namespace() {
    local namespace="$1"
    for excl in "${EXCLUDED_NAMESPACES[@]}"; do
        if [[ "$namespace" == "$excl" ]]; then
            return 0
        fi
    done
    return 1
}

# Function to delete Custom Resources (CRs) in the relevant namespaces
delete_custom_resources() {
    local crd=$1
    local resource_kind=$(echo "$crd" | cut -d '.' -f 1)

    echo "Deleting Custom Resources of kind: $resource_kind"

    for namespace in $(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}'); do
        echo "Processing namespace: $namespace"

        crs=$(kubectl get "$resource_kind" -n "$namespace" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)
        for cr in $crs; do
            echo "Deleting $resource_kind $cr in namespace $namespace"
            kubectl delete "$resource_kind" "$cr" -n "$namespace" --timeout=10s || true
        done
    done
}

# Function to delete Custom Resource Definitions (CRDs) related to 'kyma-project'
delete_custom_resource_definitions() {
    local crd=$1

    echo "Deleting Custom Resource Definition: $crd"
    kubectl delete crd "$crd" --timeout="10s" || true
}

## Main script starts here ##

# Remove Custom Resource Definitions (CRDs) that contain 'kyma-project'
echo "### Removing CRDs related to 'kyma-project'. ###"

retries=0
while [ $retries -lt $MAX_RETRIES ]; do
    # Get the list of CRDs that match the filter keyword
    crds=$(kubectl get crds -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep "kyma-project") || true

    # Check if there are any CRDs to process
    if [ -z "$crds" ]; then
        echo "## No CRDs found. ##"
        break
    fi

    for crd in $crds; do
        echo "## Processing CRD: $crd ##"
        # Delete Custom Resources associated with the CRD
        delete_custom_resources "$crd"

        # Delete the CRDs
        delete_custom_resource_definitions "$crd"
    done
    retries=$((retries + 1))
done

# List all namespaces and clean up resources in non-excluded namespaces
echo "### Cleaning up resources in non-critical namespaces. ###"
for namespace in $(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}'); do
    if ! is_excluded_namespace "$namespace"; then
        echo "## Cleaning up resources in namespace: $namespace. ##"
        echo "Deleting all resources."
        kubectl delete all --all --namespace="$namespace" || true
        echo "Deleting all pvcs."
        kubectl delete pvc --all --namespace="$namespace" || true
        echo "Deleting all configmaps."
        kubectl delete configmap --all --namespace="$namespace" || true
        echo "Deleting all secrets."
        kubectl delete secret --all --namespace="$namespace" || true
        echo "Deleting all serviceaccounts."
        kubectl delete serviceaccount --all --namespace="$namespace" || true
        echo "Deleting all roles."
        kubectl delete networkpolicy --all --namespace="$namespace" || true
    fi
done

echo "### Deleting all non-critical namespaces. ###"
kubectl get namespaces --no-headers | awk -v excl="$EXCLUDED_REGEX" '$1 !~ excl {print $1}' | xargs -r kubectl delete namespace

echo "### Cleanup completed! ###"