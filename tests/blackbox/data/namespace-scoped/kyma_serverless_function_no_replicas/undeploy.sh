#!/bin/bash

echo "## Undeploying function_no_replicas scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
