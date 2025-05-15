#!/bin/bash

echo "## Undeploy kyma_subscription_invalid_source scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
