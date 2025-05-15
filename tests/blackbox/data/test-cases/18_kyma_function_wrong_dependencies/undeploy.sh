#!/bin/bash

echo "## Undeploy 18_kyma_function_wrong_dependencies scenario ##"
kubectl delete --timeout=120s --wait=false -f resources.yaml
