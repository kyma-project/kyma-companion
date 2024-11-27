#!/bin/bash

echo "## Undeploying nginx_wrong_image scenario ##"
kubectl delete -f deployment.yml
