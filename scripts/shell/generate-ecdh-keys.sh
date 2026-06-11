#!/usr/bin/env bash
# Generate an ECDSA P-521 private key for ECDH key exchange
# (ECDSA, P-521/secp521r1, PKCS8 encoding).
#
# This script produces a PEM (PKCS8) encoded EC private key for local
# development / testing.
#
# Output file:
#   <output_dir>/encryption_key.pem  — PEM-encoded PKCS8 EC private key
#
# Usage:
#   ./generate-ecdh-keys.sh [output_dir]
#   output_dir defaults to ./config

set -euo pipefail

OUTPUT_DIR="${1:-./config}"

TMP_PEM=$(mktemp)
trap 'rm -f "$TMP_PEM"' EXIT

# Generate EC private key on the P-521 (secp521r1) curve.
openssl ecparam -name secp521r1 -genkey -noout -out "$TMP_PEM"

# Convert to PKCS8 PEM (matches cert-manager's PKCS8 encoding).
openssl pkcs8 -topk8 -nocrypt -in "$TMP_PEM" -outform PEM \
    > "$OUTPUT_DIR/encryption_key.pem"

echo "Private key written to: $OUTPUT_DIR/encryption_key.pem"
