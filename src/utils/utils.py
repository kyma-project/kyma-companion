import json
import uuid
from typing import Any

import jwt


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


def parse_k8s_token(token: str) -> Any:
    """Decode the JWT token without verification."""
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception as e:
        raise ValueError("Failed to parse k8s token") from e


def get_user_identifier_from_token(token: str) -> str:
    """Get the user identifier from the token."""
    try:
        payload = parse_k8s_token(token)
        if "sub" in payload and payload["sub"] != "":
            return str(payload["sub"])
        elif "email" in payload and payload["email"] != "":
            return str(payload["email"])
        elif (
            "kubernetes.io/serviceaccount/service-account.name" in payload
            and payload["kubernetes.io/serviceaccount/service-account.name"] != ""
        ):
            return str(payload["kubernetes.io/serviceaccount/service-account.name"])
        raise Exception("Invalid token: User identifier not found in token")
    except Exception as e:
        raise ValueError("Failed to get user identifier from token") from e
