#!/bin/bash

echo "## Undeploying wrong-rbac-permissions scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
