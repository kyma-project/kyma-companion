#!/bin/bash

echo "## Undeploying role-missing scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
