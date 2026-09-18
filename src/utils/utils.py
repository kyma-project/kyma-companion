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


def string_to_bool(value: str) -> bool:
    """Convert a string to a boolean value."""
    if value.lower() in ["true", "1", "t", "y", "yes"]:
        return True
    if value.lower() in ["false", "0", "f", "n", "no"]:
        return False
    raise ValueError(f"{value} is not a valid boolean value.")
