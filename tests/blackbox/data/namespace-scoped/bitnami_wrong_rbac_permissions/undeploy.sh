#!/bin/bash

echo "## Undeploying wrong-rbac-permissions scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
