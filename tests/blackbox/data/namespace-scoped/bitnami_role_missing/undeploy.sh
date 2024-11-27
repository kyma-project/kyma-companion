#!/bin/bash

echo "## Undeploying role-missing scenario ##"
kubectl delete -f deployment.yml
