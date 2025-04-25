#!/bin/bash

echo "## Undeploy kyma_subscription_invalid_sink scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
