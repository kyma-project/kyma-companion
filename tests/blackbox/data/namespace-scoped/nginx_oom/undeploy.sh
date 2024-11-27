#!/bin/bash

echo "## Undeploying nginx_oom scenario ##"
kubectl delete -f deployment.yml
