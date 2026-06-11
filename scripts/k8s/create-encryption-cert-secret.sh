#!/bin/bash

# Check if the COMPANION_ENCRYPTION_KEY_BASE64 env is set.
if [ -z "$COMPANION_ENCRYPTION_KEY_BASE64" ]; then
  echo "Error: COMPANION_ENCRYPTION_KEY_BASE64 is not set."
  exit 1
fi

cat <<EOF | kubectl apply -f -
apiVersion: v1
data:
  tls.key: "$COMPANION_ENCRYPTION_KEY_BASE64"
  tls.crt: ZHVtbXkK
kind: Secret
metadata:
  name: kyma-companion-encryption-cert
  namespace: ai-system
type: kubernetes.io/tls
EOF
