#!/bin/bash

echo "## Undeploying no-kubectl-binary scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
