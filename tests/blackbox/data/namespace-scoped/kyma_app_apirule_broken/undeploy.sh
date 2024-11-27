#!/bin/bash

echo "## Undeploying app_apirule_broken scenario ##"
kubectl delete -f deployment.yml
