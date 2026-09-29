#!/bin/bash

echo "## Undeploying app_serverless_syntax_err scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
