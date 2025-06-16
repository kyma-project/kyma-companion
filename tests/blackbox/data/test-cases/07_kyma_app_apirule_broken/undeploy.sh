#!/bin/bash

echo "## Undeploying app_apirule_broken scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
