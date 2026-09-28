#!/bin/bash

echo "## Undeploying nginx_wrong_image scenario ##"
kubectl delete --ignore-not-found --timeout=600s -f deployment.yml
