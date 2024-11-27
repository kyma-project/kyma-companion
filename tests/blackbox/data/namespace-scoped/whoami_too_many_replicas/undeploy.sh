#!/bin/bash

echo "## Undeploying too-many-replicas scenario ##"
kubectl delete -f deployment.yml
