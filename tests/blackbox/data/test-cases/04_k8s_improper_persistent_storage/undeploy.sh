#!/bin/bash

echo "## Undeploying k8s_improper_persistent_storage scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
