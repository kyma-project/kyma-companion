#!/bin/bash

echo "## Undeploy 18_kyma_function_wrong_dependencies scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
