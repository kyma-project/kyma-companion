#!/usr/bin/env python3
"""
Generate config/encryption_key.pem from the Base64-encoded private key in config/config.json.

The ENCRYPTION_PRIVATE_KEY_B64 field in config.json holds a PKCS#8 DER private key
encoded in Base64. This script wraps it in PEM format and writes it to the path
expected by KeyStore (config/encryption_key.pem), which is gitignored.

Usage:
    python3 scripts/python/generate_encryption_key_pem.py
"""

import base64
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = REPO_ROOT / "config" / "config.json"
OUTPUT_FILE = REPO_ROOT / "config" / "encryption_key.pem"


def main() -> None:
    """Read the Base64-encoded private key from config.json and write it as a PEM file."""
    if not CONFIG_FILE.exists():
        print(f"Error: config file not found at {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text())
    b64 = config.get("ENCRYPTION_PRIVATE_KEY_B64")
    if not b64:
        print("Error: ENCRYPTION_PRIVATE_KEY_B64 not found in config.json", file=sys.stderr)
        sys.exit(1)

    der = base64.b64decode(b64)
    pem = b"-----BEGIN PRIVATE KEY-----\n" + base64.encodebytes(der) + b"-----END PRIVATE KEY-----\n"  # gitleaks:allow
    OUTPUT_FILE.write_bytes(pem)
    print(f"Written {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
