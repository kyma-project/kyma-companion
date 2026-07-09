#!/usr/bin/env python3
"""
Encrypt K8s headers via ECDH + AES-256-GCM and print the 4 encrypted values.

Usage:
    python3 scripts/encrypt_k8s_headers.py

Required environment variables:
    TEST_CLUSTER_URL
    TEST_CLUSTER_CERTIFICATE_AUTHORITY_DATA
    TEST_CLUSTER_TOKEN
    COMPANION_API_URL
    COMPANION_TOKEN_URL
    COMPANION_CLIENT_ID
    COMPANION_CLIENT_SECRET

Output (stdout, one per line):
    X_ENCRYPTED_KEY=<base64>
    X_CLIENT_IV=<base64>
    X_TARGET_CLUSTER_ENCRYPTED=<base64>
    X_SESSION_ID=<value>
"""

import base64
import json
import os
import sys
from http import HTTPStatus

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA384
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from dotenv import load_dotenv

load_dotenv()


def get_oauth_access_token(token_url: str, client_id: str, client_secret: str) -> str:
    """Fetch an OAuth2 client-credentials access token from the given token URL."""
    response = requests.post(
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
    )
    if response.status_code != HTTPStatus.OK:
        raise ValueError(f"Failed to fetch OAuth token (status: {response.status_code}): {response.text}")

    token_response = response.json()
    access_token = token_response.get("access_token")
    if not access_token:
        raise ValueError("OAuth token response missing 'access_token'")

    return access_token


def encrypt_k8s_headers(k8s_headers: dict, companion_api_url: str, access_token: str) -> dict:
    """Encrypt K8s header values using ECDH key exchange and AES-256-GCM, returning the encrypted header dict."""
    # Generate ephemeral ECDH key pair
    client_private_key = ec.generate_private_key(ec.SECP521R1())
    client_public_key_bytes = client_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    client_public_key_b64 = base64.b64encode(client_public_key_bytes).decode()

    # Exchange public key with companion API
    response = requests.post(
        f"{companion_api_url}/api/public-key",
        json={"public_key": client_public_key_b64},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code != HTTPStatus.OK:
        raise ValueError(f"Failed to fetch public key (status: {response.status_code}): {response.text}")

    resp_data = response.json()
    session_id = resp_data["session_id"]
    server_public_key_b64 = resp_data["companion_public_key"]
    server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP521R1(),
        base64.b64decode(server_public_key_b64),
    )

    # ECDH → shared key via HKDF-SHA384
    shared_secret = client_private_key.exchange(ec.ECDH(), server_public_key)
    shared_key = HKDF(
        algorithm=SHA384(),
        length=32,
        salt=None,
        info=b"ecdh-key-exchange",
    ).derive(shared_secret)

    # Generate AES session key and IVs
    aes_key = os.urandom(32)
    payload_iv = os.urandom(12)
    key_nonce = os.urandom(12)

    # Wrap AES key with shared key
    wrapped_aes_key = key_nonce + AESGCM(shared_key).encrypt(key_nonce, aes_key, None)

    # Encrypt the K8s headers payload
    payload = json.dumps(k8s_headers).encode("utf-8")
    encrypted_payload = AESGCM(aes_key).encrypt(payload_iv, payload, None)

    return {
        "x-encrypted-key": base64.b64encode(wrapped_aes_key).decode(),
        "x-client-iv": base64.b64encode(payload_iv).decode(),
        "x-target-cluster-encrypted": base64.b64encode(encrypted_payload).decode(),
        "x-session-id": session_id,
    }


def get_required_env(name: str) -> str:
    """Return the value of a required environment variable, exiting with an error if it is unset or empty."""
    value = os.environ.get(name)
    if not value:
        print(f"Error: {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value.strip().strip("'\"")


if __name__ == "__main__":
    cluster_url = get_required_env("TEST_CLUSTER_URL")
    ca_data = get_required_env("TEST_CLUSTER_CERTIFICATE_AUTHORITY_DATA")
    token = get_required_env("TEST_CLUSTER_TOKEN")
    companion_url = get_required_env("COMPANION_API_URL")
    token_url = get_required_env("COMPANION_TOKEN_URL")
    client_id = get_required_env("COMPANION_CLIENT_ID")
    client_secret = get_required_env("COMPANION_CLIENT_SECRET")

    k8s_headers = {
        "x-cluster-url": cluster_url,
        "x-cluster-certificate-authority-data": ca_data,
        "x-k8s-authorization": token,
    }

    try:
        oauth_token = get_oauth_access_token(token_url, client_id, client_secret)
        result = encrypt_k8s_headers(k8s_headers, companion_url, oauth_token)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Print as KEY=VALUE for shell consumption
    print("\n----------------\nEncrypted K8s Headers:\n----------------\n")
    print(f'"x-encrypted-key": "{result["x-encrypted-key"]}",')
    print(f'"x-client-iv": "{result["x-client-iv"]}",')
    print(f'"x-target-cluster-encrypted": "{result["x-target-cluster-encrypted"]}",')
    print(f'"x-session-id": "{result["x-session-id"]}"')
    print("\n----------------\nUse these values in your A2A request metadata:\n----------------")
