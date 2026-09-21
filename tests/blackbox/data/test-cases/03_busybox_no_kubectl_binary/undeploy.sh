#!/bin/bash

echo "## Undeploying no-kubectl-binary scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
