#! /bin/bash

# Test - API v1 resources: GET /api/v1/resources
{ # try

    curl -s --request GET --url "http://localhost:32000/api/v1/resources" --header "Content-Type: application/json" | jq .
    #save your output

} || { # catch
    POD=$(kubectl get pod -n ai-core -l app=ai-backend -o jsonpath="{.items[0].metadata.name}")
    kubectl describe pod $POD -n ai-core
    kubectl logs $POD -n ai-core
}
