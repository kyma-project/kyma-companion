#!/bin/bash

echo "## Undeploying nginx_oom scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
