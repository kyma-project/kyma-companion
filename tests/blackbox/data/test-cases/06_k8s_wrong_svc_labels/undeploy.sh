#!/bin/bash

echo "## Undeploying k8s_wrong_svc_labels scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
