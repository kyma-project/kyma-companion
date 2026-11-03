import re


def remove_parentheses(text: str) -> str:
    """Remove text within parentheses () from a string.
    Example: 'Hello (world)' -> 'Hello '
    Example: 'React (JavaScript library)' -> 'React '"""
    return re.compile(r"\([^\[\]\(\)\{\}]+?\)").sub("", text)


def remove_brackets(text: str) -> str:
    """Remove text within square brackets [] from a string.
    Example: 'Python [programming language]' -> 'Python '
    Example: 'TypeScript [4.0.3]' -> 'TypeScript '"""
    return re.compile(r"\[[^\[\]\(\)\{\}]+?\]").sub("", text)


def remove_braces(text: str) -> str:
    """Remove text within curly braces {} from a string.
    Example: 'Hello {name}' -> 'Hello '
    Example: 'CSS {color: blue}' -> 'CSS '"""
    return re.compile(r"\{[^\[\]\(\)\{\}]+?\}").sub("", text)


def remove_header_brackets(input_text: str) -> str:
    """
    Some headers have vitepress markups and hooks.
    These usually appear in curly braces, but some images have other braces.
    However, if the header is a function name, it has empty brackets.

    Therefore all brackets (), {}, [] shall be removed, if not empty.

    This will only be applied to the header texts.
    """
    temp_text = input_text
    current_length = len(temp_text)
    while True:
        temp_text = remove_parentheses(temp_text)
        temp_text = remove_brackets(temp_text)
        temp_text = remove_braces(temp_text)
        # Check whether anything was removed.
        if len(temp_text) < current_length:
            current_length = len(temp_text)
        else:
            break
    return temp_text


def extract_first_title(text: str) -> str | None:
    """Extract the first markdown header title from the text.

    Args:
        text: The markdown text to extract the title from.

    Returns:
        The title text without the header markers (#), or None if no title is found.

    Examples:
        >>> extract_first_title("# Title 1\\nContent")
        'Title 1'
        >>> extract_first_title("## Subtitle\\nContent")
        'Subtitle'
        >>> extract_first_title("No title here")
        None
        >>> extract_first_title("  # Title with spaces\\nContent")
        'Title with spaces'
    """
    # Match any header level (# to ######) with optional leading whitespace
    header_pattern = re.compile(r"^\s*#{1,6}\s+(.+?)(?:\n|$)", re.MULTILINE)
    match = header_pattern.search(text)
    if match:
        return match.group(1).strip()
    return None
