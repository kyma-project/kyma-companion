#!/bin/bash

echo "## Undeploying kyma_subscription_old_event_type scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
