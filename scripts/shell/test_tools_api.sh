#!/bin/bash

# Test script for K8s and Kyma Tools API
# Reads configuration from config/config.json

# Read configuration values
CONFIG_FILE="config/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.json not found at $CONFIG_FILE"
    exit 1
fi

# Extract values using jq (or python if jq not available)
if command -v jq &> /dev/null; then
    CLUSTER_URL=$(jq -r '.TEST_CLUSTER_URL' "$CONFIG_FILE")
    CLUSTER_CA=$(jq -r '.TEST_CLUSTER_CA_DATA' "$CONFIG_FILE")
    AUTH_TOKEN=$(jq -r '.TEST_CLUSTER_AUTH_TOKEN' "$CONFIG_FILE")
else
    # Fallback to python if jq not available
    CLUSTER_URL=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['TEST_CLUSTER_URL'])")
    CLUSTER_CA=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['TEST_CLUSTER_CA_DATA'])")
    AUTH_TOKEN=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['TEST_CLUSTER_AUTH_TOKEN'])")
fi

# API base URL
BASE_URL="http://localhost:8000"

echo "=========================================="
echo "Testing K8s and Kyma Tools API"
echo "=========================================="
echo "Cluster URL: $CLUSTER_URL"
echo "Base URL: $BASE_URL"
echo ""

# Test K8s Tools API
echo "=========================================="
echo "K8s Tools API Tests"
echo "=========================================="

# 1. Query K8s Resources (Deployments)
echo ""
echo "1. Testing K8s Query - List Deployments in default namespace..."
curl -s -X POST "$BASE_URL/api/tools/k8s/query" \
  -H "Content-Type: application/json" \
  -H "x-cluster-url: $CLUSTER_URL" \
  -H "x-cluster-certificate-authority-data: $CLUSTER_CA" \
  -H "x-k8s-authorization: $AUTH_TOKEN" \
  -d '{"uri": "/apis/apps/v1/namespaces/default/deployments"}' | jq '.' || echo "Failed"

# 2. Get Pod Logs (requires a pod name - dynamically find first pod)
echo ""
echo "2. Testing K8s Pod Logs - Fetch logs from a pod..."

# First, query to get list of pods and extract the first pod name
PODS_RESPONSE=$(curl -s -X POST "$BASE_URL/api/tools/k8s/query" \
  -H "Content-Type: application/json" \
  -H "x-cluster-url: $CLUSTER_URL" \
  -H "x-cluster-certificate-authority-data: $CLUSTER_CA" \
  -H "x-k8s-authorization: $AUTH_TOKEN" \
  -d '{"uri": "/api/v1/namespaces/default/pods"}')

# Extract first pod name using jq or python
if command -v jq &> /dev/null; then
    POD_NAME=$(echo "$PODS_RESPONSE" | jq -r '.data.items[0].metadata.name // empty' 2>/dev/null)
else
    POD_NAME=$(echo "$PODS_RESPONSE" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('data',{}).get('items',[{}])[0].get('metadata',{}).get('name',''))" 2>/dev/null)
fi

if [ -z "$POD_NAME" ] || [ "$POD_NAME" = "null" ]; then
    echo "Skipping logs test - no pods found in default namespace"
else
    echo "Found pod: $POD_NAME"
    echo "Fetching logs..."
    curl -s -X POST "$BASE_URL/api/tools/k8s/logs/pods" \
      -H "Content-Type: application/json" \
      -H "x-cluster-url: $CLUSTER_URL" \
      -H "x-cluster-certificate-authority-data: $CLUSTER_CA" \
      -H "x-k8s-authorization: $AUTH_TOKEN" \
      -d "{\"name\": \"$POD_NAME\", \"namespace\": \"default\", \"tail_lines\": 10}" | jq '.' || echo "Failed"
fi

# 3. Get Cluster Overview
echo ""
echo "3. Testing K8s Overview - Cluster Level..."
curl -s -X POST "$BASE_URL/api/tools/k8s/overview" \
  -H "Content-Type: application/json" \
  -H "x-cluster-url: $CLUSTER_URL" \
  -H "x-cluster-certificate-authority-data: $CLUSTER_CA" \
  -H "x-k8s-authorization: $AUTH_TOKEN" \
  -d '{"namespace": "", "resource_kind": "cluster"}' | jq '.' || echo "Failed"

# Test Kyma Tools API
echo ""
echo "=========================================="
echo "Kyma Tools API Tests"
echo "=========================================="

# 1. Query Kyma Resources (Functions)
echo ""
echo "1. Testing Kyma Query - List Functions..."
curl -s -X POST "$BASE_URL/api/tools/kyma/query" \
  -H "Content-Type: application/json" \
  -H "x-cluster-url: $CLUSTER_URL" \
  -H "x-cluster-certificate-authority-data: $CLUSTER_CA" \
  -H "x-k8s-authorization: $AUTH_TOKEN" \
  -d '{"uri": "/apis/serverless.kyma-project.io/v1alpha2/functions"}' | jq '.' || echo "Failed"

# 2. Get Kyma Resource Version
echo ""
echo "2. Testing Kyma Resource Version - Function..."
curl -s -X POST "$BASE_URL/api/tools/kyma/resource-version" \
  -H "Content-Type: application/json" \
  -H "x-cluster-url: $CLUSTER_URL" \
  -H "x-cluster-certificate-authority-data: $CLUSTER_CA" \
  -H "x-k8s-authorization: $AUTH_TOKEN" \
  -d '{"resource_kind": "Function"}' | jq '.' || echo "Failed"

# 3. Search Kyma Documentation
echo ""
echo "3. Testing Kyma Documentation Search..."
curl -s -X POST "$BASE_URL/api/tools/kyma/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "How to install Kyma?"}' | jq '.' || echo "Failed"

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
