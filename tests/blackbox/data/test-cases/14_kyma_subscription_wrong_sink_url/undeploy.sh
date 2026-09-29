#!/bin/bash

echo "## Undeploying kyma_subscription_old_event_type scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
