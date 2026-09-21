#!/bin/bash

echo "## Undeploying nginx_oom scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
