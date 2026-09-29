#!/bin/bash

echo "## Undeploying function_no_replicas scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
