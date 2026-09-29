#!/bin/bash

echo "## Undeploying role-missing scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
