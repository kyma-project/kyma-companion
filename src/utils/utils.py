import hashlib
import json
import uuid
from collections.abc import Sequence
from typing import Any

import jwt
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from langchain_core.messages import BaseMessage

JWT_TOKEN_SUB = "sub"
JWT_TOKEN_EMAIL = "email"
JWT_TOKEN_SERVICE_ACCOUNT = "kubernetes.io/serviceaccount/service-account.name"
CN_KEYS = ["common_name", "commonName"]


def create_ndjson_str(obj: dict) -> str:
    """
    Converts the object to Newline-delimited JSON (ndjson) format.
    e.g. {"name": "Alice"} -> '{"name": "Alice"}\n'
    Args:
        obj (dict): The JSON object.
    Returns:
        str: A stringified Newline-delimited JSON.
    """
    return f"{json.dumps(obj)}\n"


def create_session_id() -> str:
    """
    Generates a new session ID.
    Returns:
        str: A new session ID.
    """
    return str(uuid.uuid4().hex)


def is_empty_str(data: str | None) -> bool:
    """Check if the string is None or empty."""
    return data is None or data == "" or data.strip() == ""


def is_non_empty_str(data: str | None) -> bool:
    """Check if the string is not None and not empty."""
    return data is not None and data.strip() != ""


def string_to_bool(value: str) -> bool:
    """Convert a string to a boolean value."""
    if value.lower() in ["true", "1", "t", "y", "yes"]:
        return True
    if value.lower() in ["false", "0", "f", "n", "no"]:
        return False
    raise ValueError(f"{value} is not a valid boolean value.")


def to_sequence_messages(
    messages: (
        list[BaseMessage | list[str] | tuple[str, str] | str | dict[str, Any]]
        | BaseMessage
        | list[str]
        | tuple[str, str]
        | str
        | dict[str, Any]
    ),
) -> Sequence[BaseMessage]:
    """
    Convert messages to a sequence of BaseMessage.
    """

    if isinstance(messages, BaseMessage):
        return [messages]

    result = []
    for _, message in enumerate(messages):
        if isinstance(message, BaseMessage):
            result.append(message)
        else:
            raise ValueError(f"Unsupported message type: {type(message)} in to_sequence_messages")
    return result


def parse_k8s_token(token: str) -> Any:
    """Decode the JWT token without verification."""
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception as e:
        raise ValueError("Failed to parse k8s token") from e


def generate_sha256_hash(data: str) -> str:
    """Generate a SHA256 hash of the input string."""
    # Create a new sha256 hash object
    sha256_hash = hashlib.sha256()
    # Update the hash object with the bytes-like object (encoded string)
    sha256_hash.update(data.encode())
    # Return the hexadecimal digest of the hash
    return sha256_hash.hexdigest()


def get_user_identifier_from_token(token: str) -> str:
    """Get the user identifier from the token. The output is a SHA256 hash of the user identifier."""
    try:
        payload = parse_k8s_token(token)
        if JWT_TOKEN_SUB in payload and payload[JWT_TOKEN_SUB] != "":
            return generate_sha256_hash(str(payload[JWT_TOKEN_SUB]))
        elif JWT_TOKEN_EMAIL in payload and payload[JWT_TOKEN_EMAIL] != "":
            return generate_sha256_hash(str(payload[JWT_TOKEN_EMAIL]))
        elif JWT_TOKEN_SERVICE_ACCOUNT in payload and payload[JWT_TOKEN_SERVICE_ACCOUNT] != "":
            return generate_sha256_hash(str(payload[JWT_TOKEN_SERVICE_ACCOUNT]))
        raise ValueError("Invalid token: User identifier not found in token")
    except Exception as e:
        raise ValueError("Failed to get user identifier from token") from e


def get_user_identifier_from_client_certificate(client_certificate_data: bytes) -> str:
    """Get the user identifier from the client certificate. The output is a SHA256 hash of the user identifier."""
    try:
        cert = x509.load_pem_x509_certificate(client_certificate_data, default_backend())
        # check if the Common Name (CN) is present in the subject.
        for name in cert.subject:
            if name.oid._name in CN_KEYS and name.value != "":
                return generate_sha256_hash(str(name.value))
        if str(cert.serial_number) != "":
            return generate_sha256_hash(str(cert.serial_number))
        raise ValueError("Invalid client certificate: User identifier not found in certificate")
    except Exception as e:
        raise ValueError("Failed to get user identifier from client certificate") from e
