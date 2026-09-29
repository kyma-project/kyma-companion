#!/bin/bash

echo "## Undeploying k8s_wrong_svc_labels scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
