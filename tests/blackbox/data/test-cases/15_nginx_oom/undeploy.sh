#!/bin/bash

echo "## Undeploying test-deployment-15 scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
