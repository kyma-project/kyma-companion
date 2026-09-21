#!/bin/bash

echo "## Undeploying k8s_incorrect_liveness_probe scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
