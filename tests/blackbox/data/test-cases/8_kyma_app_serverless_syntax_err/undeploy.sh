#!/bin/bash

echo "## Undeploying app_serverless_syntax_err scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
