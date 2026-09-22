#!/bin/bash

echo "## Undeploy kyma_subscription_invalid_source scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
