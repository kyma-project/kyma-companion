#!/bin/bash

echo "## Undeploying nginx_wrong_image scenario ##"
kubectl delete --timeout=120s --wait=false -f deployment.yml
