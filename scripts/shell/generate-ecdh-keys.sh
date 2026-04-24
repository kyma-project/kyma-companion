#!/usr/bin/env bash
# Generate an ECDSA P-256 private key matching the cert-manager Certificate CR
# (ECDSA, P-256, PKCS8 encoding).
#
# cert-manager stores the key as PEM (PKCS8) in the tls.key field of the
# Kubernetes secret.  This script produces the same format for local
# development / testing.
#
# Output file:
#   <output_dir>/tls.key  — PEM-encoded PKCS8 EC private key
#
# Usage:
#   ./generate-ecdh-keys.sh [output_dir]
#   output_dir defaults to ./ecdh-keys

set -euo pipefail

OUTPUT_DIR="${1:-./ecdh-keys}"
mkdir -p "$OUTPUT_DIR"

TMP_PEM=$(mktemp)
trap 'rm -f "$TMP_PEM"' EXIT

# Generate EC private key on the P-256 (prime256v1 / secp256r1) curve.
openssl ecparam -name prime256v1 -genkey -noout -out "$TMP_PEM"

# Convert to PKCS8 PEM (matches cert-manager's PKCS8 encoding).
openssl pkcs8 -topk8 -nocrypt -in "$TMP_PEM" -outform PEM \
    > "$OUTPUT_DIR/tls.key"

echo "Private key written to: $OUTPUT_DIR/tls.key"
