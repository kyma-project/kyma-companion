#!/bin/bash

echo "## Undeploying wrong-event-type scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
