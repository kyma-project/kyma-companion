#!/bin/bash

echo "## Undeploying function_no_replicas scenario ##"
kubectl delete -f deployment.yml
