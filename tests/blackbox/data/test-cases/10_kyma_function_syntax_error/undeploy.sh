#!/bin/bash

echo "## Undeploy kyma_function_syntax_error scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
