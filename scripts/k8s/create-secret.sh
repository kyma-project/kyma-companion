#!/bin/bash

# Check if the COMPANION_CONFIG_BASE64 env is set.
if [ -z "$COMPANION_CONFIG_BASE64" ]; then
  echo "Error: COMPANION_CONFIG_BASE64 is not set."
fi

echo "Creating secret companion-config in ai-system namespace."
# create a secret with the base64 encoded file.
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: companion-config
  namespace: ai-system
type: Opaque
data:
  "companion-config.json": "$COMPANION_CONFIG_BASE64"
EOF
