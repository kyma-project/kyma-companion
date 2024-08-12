import os


def get_env(key: str, required: bool = True, default: str = "") -> str:
    value = os.environ.get(key)
    if value is None or value == "":
        if required:
            raise ValueError(f"ERROR: Env {key} is missing")
        return default
    return value
