#!/bin/bash

echo "## Undeploying wrong-event-type scenario ##"
kubectl delete -f deployment.yml
