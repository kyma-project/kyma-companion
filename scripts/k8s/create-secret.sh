#!/bin/bash

# Check if the COMPANION_CONFIG_PATH env is set.
if [ -z "$COMPANION_CONFIG_PATH" ]; then
  COMPANION_CONFIG_PATH="../../config/config.json"
  echo "Warn: COMPANION_CONFIG_PATH is not set. Using default: $COMPANION_CONFIG_PATH."
  echo "NOTE: You can find the companion-kcp-dev-config.json file in AIForce SharePoint"
else
  echo "COMPANION_CONFIG_PATH is set to '$COMPANION_CONFIG_PATH'."
fi

# check that the file exists
if [ ! -f "$COMPANION_CONFIG_PATH" ]; then
  echo "Error: $COMPANION_CONFIG_PATH file does not exist."
  exit 1
fi

# base64 encode the file and save it to a variable.
COMPANION_CONFIG_BASE64="$(cat $COMPANION_CONFIG_PATH | jq -c | base64)"

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
