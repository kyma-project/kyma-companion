#!/bin/bash

echo "## Undeploying k8s_improper_persistent_storage scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
