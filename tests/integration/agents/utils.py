import ast
import json
from typing import Any


def convert_string_to_object(input_string: str) -> Any:
    """Try to convert string to object."""
    # First, try using json.loads (works for proper JSON strings)
    try:
        return json.loads(input_string)
    except Exception:
        # If JSON parsing fails
        try:
            return ast.literal_eval(input_string)
        except (SyntaxError, ValueError):
            # If it's not valid JSON or a Python literal, return the string itself
            return input_string
