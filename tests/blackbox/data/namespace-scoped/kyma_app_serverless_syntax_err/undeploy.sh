#!/bin/bash

echo "## Undeploying app_serverless_syntax_err scenario ##"
kubectl delete -f deployment.yml
