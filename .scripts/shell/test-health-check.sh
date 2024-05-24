#! /bin/bash

# Test - Health check: GET /api/v1/health/check
{ # try

    curl --request GET --url "http://localhost:32000/api/v1/health/check" --header "Content-Type: application/json"
    #save your output

} || { # catch
    POD=$(kubectl get pod -n ai-core -l app=ai-backend -o jsonpath="{.items[0].metadata.name}")
    kubectl describe pod $POD -n ai-core
    kubectl logs $POD -n ai-core
}
