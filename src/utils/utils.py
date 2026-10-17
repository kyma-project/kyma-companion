import uuid


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
