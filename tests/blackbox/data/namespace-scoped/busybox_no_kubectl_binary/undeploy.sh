#!/bin/bash

echo "## Undeploying no-kubectl-binary scenario ##"
kubectl delete -f deployment.yml
