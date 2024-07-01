#! /bin/bash

MAX_RUN=$1

# Wait for deployment
sleep 15
# Get deployed pod name
POD=$(kubectl get pod -n ai-core -l app=ai-backend -o jsonpath="{.items[0].metadata.name}")
# Set running counter
RUN_COUNTER=0
# Get pod status
kubectl get pods $POD -n ai-core -o 'jsonpath={.status.containerStatuses[0]}' | jq .
# Wait for pod to be ready or timeout
while [[ $(kubectl get pods $POD -n ai-core -o 'jsonpath={..status.conditions[?(@.type=="Ready")].status}') != "True" ]] && [[ "$MAX_RUN" -gt "$RUN_COUNTER" ]]; do
    sleep 1
    RUN_COUNTER=$((RUN_COUNTER + 1))
    echo "$RUN_COUNTER / $MAX_RUN - Waiting for the pod to be ready"
    kubectl get pods $POD -n ai-core -o 'jsonpath={.status.containerStatuses[0]}' | jq .
done
# Get service
kubectl get svc -n ai-core
# Get pods
kubectl get pods -n ai-core
