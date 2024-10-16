#!/usr/bin/env bash

# standard bash error handling
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

# create k3d cluster.
k3d cluster create --config ./tests/integration/k3d-config.yaml

# create a static kubeconfig for the test user.
USER_NAME="test-user1"
CONTEXT=$(kubectl config current-context)
CLUSTER=$(kubectl config view -o json | jq -r --arg context "${CONTEXT}" '.contexts[] | select(.name == $context) | .context.cluster')
URL=$(kubectl config view -o json | jq -r --arg cluster "${CLUSTER}" '.clusters[] | select(.name == $cluster) | .cluster.server')
SERVICE_ACCOUNT="$USER_NAME-admin"
kubectl -n default create serviceaccount "$SERVICE_ACCOUNT"

kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  annotations:
    kubernetes.io/service-account.name: "$SERVICE_ACCOUNT"
  name: "$SERVICE_ACCOUNT"
  namespace: default
type: kubernetes.io/service-account-token
EOF

kubectl create clusterrolebinding "$SERVICE_ACCOUNT" --clusterrole cluster-admin --serviceaccount "default:$SERVICE_ACCOUNT"
CA=$(kubectl get secret "$SERVICE_ACCOUNT" -o jsonpath="{.data.ca\.crt}")
TOKEN=$(kubectl get secret "$SERVICE_ACCOUNT" -o jsonpath="{.data.token}" | base64 --decode)

# export the cluster details.
export K3d_URL="$URL"
export K3d_CA_DATA="$CA"
export K3d_AUTH_TOKEN="$TOKEN"

# save .env file for integration tests.
ENV_FILE_NAME=".env.integration.tests"
rm -f "$ENV_FILE_NAME"
echo "saving K3d cluster data to: $ENV_FILE_NAME"
echo "K3d_URL=\"$URL\"
K3d_CA_DATA=\"$CA\"
K3d_AUTH_TOKEN=\"$TOKEN\"" >> "$ENV_FILE_NAME"

# create integration test fixtures.
kubectl apply -f ./tests/integration/fixtures/.
