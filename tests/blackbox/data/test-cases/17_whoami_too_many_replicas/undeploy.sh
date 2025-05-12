#!/bin/bash

echo "## Undeploying too-many-replicas scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
