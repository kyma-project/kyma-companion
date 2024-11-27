#!/bin/bash

echo "## Undeploying wrong-rbac-permissions scenario ##"
kubectl delete -f deployment.yml
