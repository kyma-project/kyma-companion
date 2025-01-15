#!/bin/bash

echo "## Undeploy kyma_function_syntax_error scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
