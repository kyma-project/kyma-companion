#!/usr/bin/env bash
# Generate ECDH P-256 key pairs for the companion encryption service.
#
# Output files (all values are base64-encoded, no line wrapping):
#   <output_dir>/server_private_key.b64  — PKCS8 DER private key (used by Encryption class)
#   <output_dir>/server_public_key.b64   — raw uncompressed EC point (65 bytes: 04 || X || Y)
#   <output_dir>/client_private_key.b64  — PKCS8 DER private key (for client-side use)
#   <output_dir>/client_public_key.b64   — raw uncompressed EC point (TEST_CLIENT_PUBLIC_KEY)
#
# Usage:
#   ./generate-ecdh-keys.sh [output_dir]
#   output_dir defaults to ./ecdh-keys

set -euo pipefail

OUTPUT_DIR="${1:-./ecdh-keys}"
mkdir -p "$OUTPUT_DIR"

# P-256 SubjectPublicKeyInfo DER is always 91 bytes.
# The last 65 bytes are the raw uncompressed EC point (04 || X || Y).
RAW_EC_POINT_BYTES=65

generate_key_pair() {
    local name="$1"
    local tmp_pem
    tmp_pem=$(mktemp)

    # Generate EC private key on the P-256 (prime256v1 / secp256r1) curve.
    openssl ecparam -name prime256v1 -genkey -noout -out "$tmp_pem"

    # Private key: PKCS8 DER → base64 (no line wrapping).
    openssl pkcs8 -topk8 -nocrypt -in "$tmp_pem" -outform DER \
        | base64 | tr -d '\n' \
        > "$OUTPUT_DIR/${name}_private_key.b64"

    # Public key: raw uncompressed EC point (last 65 bytes of SubjectPublicKeyInfo DER) → base64.
    openssl ec -in "$tmp_pem" -pubout -outform DER 2>/dev/null \
        | tail -c "$RAW_EC_POINT_BYTES" \
        | base64 | tr -d '\n' \
        > "$OUTPUT_DIR/${name}_public_key.b64"

    rm -f "$tmp_pem"
    echo "Generated ${name} key pair"
}

generate_key_pair "server"
generate_key_pair "client"

echo ""
echo "Keys written to: $OUTPUT_DIR"
