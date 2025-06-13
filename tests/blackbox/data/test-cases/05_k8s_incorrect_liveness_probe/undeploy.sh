#!/bin/bash

echo "## Undeploying k8s_incorrect_liveness_probe scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
