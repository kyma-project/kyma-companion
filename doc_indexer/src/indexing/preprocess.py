"""Content preprocessing for markdown documents before chunking."""

import re
from collections.abc import Callable
from urllib.parse import urljoin, urlparse


def _split_on_fences(text: str) -> list[tuple[str, bool]]:
    """Split text into segments of (content, is_code_block).

    Args:
        text: The markdown text to split.

    Returns:
        A list of (segment_text, is_code_block) tuples, alternating between
        non-code and code segments.
    """
    # Split on ``` fences (opening and closing)
    fence_pattern = re.compile(r"(```[^\n]*\n.*?```)", re.DOTALL)
    parts = fence_pattern.split(text)
    result: list[tuple[str, bool]] = []
    for i, part in enumerate(parts):
        is_code: bool = i % 2 == 1  # odd-indexed parts are code blocks
        result.append((part, is_code))
    return result


def _rejoin_segments(segments: list[tuple[str, bool]]) -> str:
    """Rejoin segments produced by _split_on_fences."""
    return "".join(text for text, _ in segments)


def _apply_outside_fences(text: str, transform: Callable[[str], str]) -> str:
    """Apply a transform function only to the non-code portions of text."""
    segments = _split_on_fences(text)
    result: list[tuple[str, bool]] = []
    for segment, is_code in segments:
        if is_code:
            result.append((segment, True))
        else:
            result.append((transform(segment), False))
    return _rejoin_segments(result)


def _remove_frontmatter(text: str) -> tuple[str, str | None]:
    """Remove YAML frontmatter block and return (cleaned_text, title_from_frontmatter).

    Args:
        text: The markdown text possibly starting with frontmatter.

    Returns:
        A tuple of (text_without_frontmatter, title_value_or_None).
    """
    frontmatter_pattern = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    match = frontmatter_pattern.match(text)
    if not match:
        return text, None

    frontmatter_body = match.group(1)
    # Extract 'title:' value from frontmatter
    title_match = re.search(r"^title:\s*['\"]?(.+?)['\"]?\s*$", frontmatter_body, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else None

    cleaned = text[match.end() :]
    return cleaned, title


def _remove_html_comments(text: str) -> str:
    """Remove HTML comments but preserve content between tabs markers.

    Handles:
    - <!-- tabs:start --> and <!-- tabs:end --> markers are removed (content kept)
    - Tab headers like #### **Title** become #### Title
    - All other HTML comments are removed entirely

    Args:
        text: Text outside of fenced code blocks.

    Returns:
        Text with HTML comments processed.
    """
    # Remove <!-- tabs:start --> and <!-- tabs:end --> markers
    text = re.sub(r"<!--\s*tabs:start\s*-->", "", text)
    text = re.sub(r"<!--\s*tabs:end\s*-->", "", text)

    # Convert tab header bold: #### **Title** -> #### Title
    # Handles both fully-bold headings and headings where only the first word(s) are bold.
    text = re.sub(r"^(#{1,6}\s+)\*\*(.+?)\*\*", r"\1\2", text, flags=re.MULTILINE)

    # Remove all remaining HTML comments (DOTALL to handle multi-line)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    return text


def _transform_callouts(text: str) -> str:
    """Convert GitHub/VitePress callout syntax to bold prefix style.

    Transforms:
      > [!WARNING] -> > **Warning:**
      > [!NOTE]    -> > **Note:**
      > [!TIP]     -> > **Tip:**
      > [!CAUTION] -> > **Caution:**

    Args:
        text: Text outside of fenced code blocks.

    Returns:
        Text with callouts transformed.
    """
    callout_map = {
        "WARNING": "Warning",
        "NOTE": "Note",
        "TIP": "Tip",
        "CAUTION": "Caution",
    }
    for key, label in callout_map.items():
        text = re.sub(
            rf"^(>\s*)\[!{key}\]",
            rf"\1**{label}:**",
            text,
            flags=re.MULTILINE,
        )
    return text


def _remove_badges(text: str) -> str:
    """Remove badge markdown: [![alt](img)](link).

    Args:
        text: Text outside of fenced code blocks.

    Returns:
        Text with badges removed.
    """
    # Match [![...](...)...](...) -- badge pattern
    badge_pattern = re.compile(r"\[!\[.*?\]\(.*?\)\]\(.*?\)")
    return badge_pattern.sub("", text)


def _transform_images(text: str) -> str:
    """Transform images: ![alt](src) -> 'Image: alt' or remove if alt is empty.

    Args:
        text: Text outside of fenced code blocks.

    Returns:
        Text with images transformed.
    """

    def replace_image(match: re.Match) -> str:
        alt: str = match.group(1).strip()
        if alt:
            return f"Image: {alt}"
        return ""

    return re.sub(r"!\[([^\]]*)\]\([^)]*\)", replace_image, text)


def _resolve_relative_links(text: str, page_url: str | None) -> str:
    """Resolve relative links against page_url.

    For [text](target) where target has no scheme:
    - Resolve against the directory of page_url
    - Drop .md suffix when page_url is a kyma-project.io URL
    - Keep #anchor parts
    - If page_url is None, return text only (drop target)

    Args:
        text: Text outside of fenced code blocks.
        page_url: The URL of the source page, or None.

    Returns:
        Text with relative links resolved or simplified.
    """
    is_kyma_docs = page_url is not None and "kyma-project.io" in page_url

    # Compute base directory URL for resolution
    if page_url is not None:
        parsed = urlparse(page_url)
        # Directory = everything up to the last '/'
        path_dir = parsed.path.rsplit("/", 1)[0] + "/"
        base_url = parsed._replace(path=path_dir, fragment="").geturl()
    else:
        base_url = None

    def replace_link(match: re.Match) -> str:
        link_text: str = match.group(1)
        target: str = match.group(2)

        # Check if target has a scheme (absolute URL)
        parsed_target = urlparse(target)
        if parsed_target.scheme:
            # Absolute URL -- leave as is
            original: str = match.group(0)
            return original

        if base_url is None:
            # No page_url given, return text only
            return link_text

        # Resolve relative URL
        resolved = urljoin(base_url, target)

        # Drop .md suffix on kyma-project.io pages
        if is_kyma_docs:
            # Only strip .md before any fragment
            resolved_parsed = urlparse(resolved)
            path = resolved_parsed.path
            if path.endswith(".md"):
                path = path[:-3]
            resolved = resolved_parsed._replace(path=path).geturl()

        return f"[{link_text}]({resolved})"

    return re.sub(r"\[([^\]]+)\]\(([^)]*)\)", replace_link, text)


def _normalize_whitespace(text: str) -> str:
    """Collapse 3+ blank lines to 2 and strip trailing spaces per line.

    Args:
        text: The full markdown text.

    Returns:
        Text with whitespace normalized.
    """
    # Strip trailing spaces from each line
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text


def preprocess_markdown(text: str, page_url: str | None = None) -> str:
    """Preprocess a markdown document before chunking.

    Applies the following transformations in order:
    1. Remove YAML frontmatter; insert # <title> if no H1 follows and frontmatter had a title
    2. Remove HTML comments (outside code fences); keep tabs content, strip bold from tab headers
    3. Transform callouts (outside code fences)
    4. Remove badges (outside code fences)
    5. Transform images (outside code fences)
    6. Resolve relative links (outside code fences)
    7. Normalize whitespace

    Args:
        text: The raw markdown text to preprocess.
        page_url: The URL of the source page (used for relative link resolution).

    Returns:
        The preprocessed markdown text.
    """
    # Step 1: Frontmatter
    text, frontmatter_title = _remove_frontmatter(text)

    # Check if the text has an H1 after frontmatter removal.
    # We split on fences here so that a '# heading' inside a code block is not
    # counted as a real H1 -- only headings in non-code segments are checked.
    has_h1 = any(
        bool(re.search(r"^#{1}\s+", segment, re.MULTILINE))
        for segment, is_code in _split_on_fences(text)
        if not is_code
    )
    if not has_h1 and frontmatter_title:
        text = f"# {frontmatter_title}\n\n{text}"

    # Steps 2-6 must only apply outside fenced code blocks
    # Step 2: HTML comments
    text = _apply_outside_fences(text, _remove_html_comments)

    # Step 3: Callouts
    text = _apply_outside_fences(text, _transform_callouts)

    # Step 4: Badges
    text = _apply_outside_fences(text, _remove_badges)

    # Step 5: Images
    text = _apply_outside_fences(text, _transform_images)

    # Step 6: Relative links
    text = _apply_outside_fences(text, lambda t: _resolve_relative_links(t, page_url))

    # Step 7: Whitespace
    text = _normalize_whitespace(text)

    return text
