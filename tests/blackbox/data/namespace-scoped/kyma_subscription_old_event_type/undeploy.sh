#!/bin/bash

echo "## Undeploying kyma_subscription_old_event_type scenario ##"
kubectl delete -f deployment.yml
