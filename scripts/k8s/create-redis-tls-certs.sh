#!/bin/bash

set -euo pipefail

OUTPUT_DIR="${1:-/tmp/redis-tls}"
mkdir -p "$OUTPUT_DIR"

# CA key + cert with proper key usage (required by Python 3.13 strict X.509 validation)
openssl genrsa -out "$OUTPUT_DIR/ca.key" 4096
openssl req -new -x509 -days 365 \
  -key "$OUTPUT_DIR/ca.key" \
  -out "$OUTPUT_DIR/ca.crt" \
  -subj "/CN=redis-test-ca" \
  -addext "basicConstraints=critical,CA:true" \
  -addext "keyUsage=critical,digitalSignature,cRLSign,keyCertSign"

# Server key + cert signed by CA
openssl genrsa -out "$OUTPUT_DIR/redis.key" 4096
openssl req -new -key "$OUTPUT_DIR/redis.key" -out "$OUTPUT_DIR/redis.csr" \
  -subj "/CN=redis.redis.svc.cluster.local"
openssl x509 -req -days 365 \
  -in "$OUTPUT_DIR/redis.csr" \
  -CA "$OUTPUT_DIR/ca.crt" \
  -CAkey "$OUTPUT_DIR/ca.key" \
  -CAcreateserial \
  -extfile <(echo "subjectAltName=DNS:redis.redis.svc.cluster.local,IP:127.0.0.1") \
  -out "$OUTPUT_DIR/redis.crt"

echo "TLS certificates written to $OUTPUT_DIR"
