"""Unit tests for content preprocessing before chunking."""

from pathlib import Path

import pytest
from indexing.adaptive_indexer import deduplicate_documents
from indexing.preprocess import preprocess_markdown
from langchain_core.documents import Document

pytestmark = pytest.mark.unit

FIXTURES_PATH = Path(__file__).parent.parent / "fixtures" / "preprocess"


def _read(filename: str) -> str:
    return (FIXTURES_PATH / filename).read_text()


class TestFrontmatter:
    """Rule 1: YAML frontmatter is removed; missing H1 is inserted from title:."""

    def test_frontmatter_removed_and_title_inserted(self) -> None:
        """SAP tutorials header with title: field -- H1 must be synthesised."""
        given = _read("frontmatter_input.md")
        expected = _read("frontmatter_expected.md")
        assert preprocess_markdown(given) == expected

    def test_no_frontmatter_unchanged(self) -> None:
        """Documents without frontmatter are returned unchanged by rule 1."""
        text = "# My Title\n\nSome content.\n"
        assert preprocess_markdown(text) == text

    def test_frontmatter_with_existing_h1_no_duplicate(self) -> None:
        """When the document already has an H1 after frontmatter, no title is prepended."""
        text = "---\ntitle: From Frontmatter\n---\n# Already Has H1\n\nContent.\n"
        result = preprocess_markdown(text)
        assert result.startswith("# Already Has H1")
        assert "From Frontmatter" not in result


class TestHtmlComments:
    """Rule 2: HTML comments are stripped; loio and similar markers disappear."""

    def test_loio_comments_removed(self) -> None:
        """BTP cloud platform loio comments must be removed entirely."""
        given = _read("html_comments_input.md")
        expected = _read("html_comments_expected.md")
        assert preprocess_markdown(given) == expected


class TestTabsBlock:
    """Rule 2 (tabs variant): VitePress tabs markers removed, content and plain headers kept."""

    def test_tabs_markers_removed_content_preserved(self) -> None:
        given = _read("tabs_input.md")
        expected = _read("tabs_expected.md")
        assert preprocess_markdown(given) == expected


class TestCallouts:
    """Rule 3: GitHub/VitePress callout syntax is converted to bold prefix."""

    def test_callouts_transformed(self) -> None:
        given = _read("callouts_input.md")
        expected = _read("callouts_expected.md")
        assert preprocess_markdown(given) == expected


class TestBadgesAndImages:
    """Rules 4 and 5: badges removed, images with alt become 'Image: alt'."""

    def test_badges_removed_images_transformed(self) -> None:
        given = _read("badges_images_input.md")
        expected = _read("badges_images_expected.md")
        assert preprocess_markdown(given) == expected

    def test_image_no_alt_removed(self) -> None:
        """An image with empty alt text is removed entirely."""
        text = "# Title\n\n![](./img.png)\n\nContent.\n"
        result = preprocess_markdown(text)
        assert "![" not in result
        assert "img.png" not in result

    def test_image_with_alt_becomes_text(self) -> None:
        """An image with alt text becomes 'Image: <alt>'."""
        text = "# Title\n\n![My diagram](./diagram.png)\n\nContent.\n"
        result = preprocess_markdown(text)
        assert "Image: My diagram" in result
        assert "diagram.png" not in result


class TestRelativeLinks:
    """Rule 6: relative links are resolved against page_url."""

    def test_relative_links_resolved_kyma_docs(self) -> None:
        """Relative links in kyma-project.io pages are resolved and .md stripped."""
        given = _read("relative_links_input.md")
        expected = _read("relative_links_expected.md")
        page_url = "https://kyma-project.io/docs/install/overview.md"
        assert preprocess_markdown(given, page_url=page_url) == expected

    def test_no_page_url_drops_target(self) -> None:
        """With page_url=None, relative link target is dropped, link text kept."""
        text = "# Title\n\nSee [the guide](./guide.md) for details.\n"
        result = preprocess_markdown(text, page_url=None)
        assert "the guide" in result
        assert "guide.md" not in result
        assert "[the guide](./guide.md)" not in result

    def test_absolute_links_unchanged(self) -> None:
        """Absolute links with a scheme are left unchanged."""
        text = "# Title\n\nVisit [example](https://example.com/page).\n"
        result = preprocess_markdown(text, page_url="https://kyma-project.io/docs/page.md")
        assert "[example](https://example.com/page)" in result


class TestCodeBlockPreservation:
    """IMPORTANT: content inside ``` fences must survive untouched."""

    def test_code_block_content_preserved(self) -> None:
        """HTML comments and markdown links inside code blocks must not be processed."""
        given = _read("code_block_input.md")
        expected = _read("code_block_expected.md")
        assert preprocess_markdown(given) == expected

    def test_comment_outside_fence_removed_inside_kept(self) -> None:
        """Demonstrate that the same syntax is handled differently inside vs outside fences."""
        text = "Before: <!-- remove me -->\n\n```python\n# <!-- keep me -->\n```\n\nAfter.\n"
        result = preprocess_markdown(text)
        assert "remove me" not in result
        assert "<!-- keep me -->" in result

    def test_link_outside_fence_resolved_inside_kept(self) -> None:
        """Markdown links outside fences are transformed; inside fences they are not."""
        text = "Outside: [text](./page.md)\n\n```\n[not](a-link.md)\n```\n"
        result = preprocess_markdown(text, page_url=None)
        # Outside: target dropped since page_url is None
        assert "[text](./page.md)" not in result
        assert "text" in result
        # Inside: unchanged
        assert "[not](a-link.md)" in result


class TestWhitespace:
    """Rule 7: 3+ blank lines collapsed to 2; trailing spaces stripped."""

    def test_three_blank_lines_collapsed(self) -> None:
        """Three or more consecutive blank lines are collapsed to two."""
        text = "# Title\n\n\n\nContent.\n"
        result = preprocess_markdown(text)
        # Must have no run of 4+ newlines (= 3+ blank lines)
        assert "\n\n\n\n" not in result
        # And must still contain at least the content (not over-collapsed)
        assert "Content." in result

    def test_trailing_spaces_stripped(self) -> None:
        """Trailing spaces on each line are removed."""
        text = "# Title   \n\nLine with trailing spaces.   \n"
        result = preprocess_markdown(text)
        for line in result.splitlines():
            assert line == line.rstrip(), f"Trailing space found on: {line!r}"


class TestDeduplication:
    """Rule 8: SHA-256 deduplication keeps the docs/user/ path on collision."""

    def test_unique_documents_kept(self) -> None:
        """Documents with different content are all retained."""
        docs = [
            Document(page_content="# Doc A\nContent A.", metadata={"source": "a.md"}),
            Document(page_content="# Doc B\nContent B.", metadata={"source": "b.md"}),
        ]
        result = deduplicate_documents(docs)
        assert len(result) == len(docs)

    def test_duplicate_keeps_first(self) -> None:
        """When two documents have the same content and neither is docs/user/, the first is kept."""
        doc_a = Document(page_content="# Same\nContent.", metadata={"source": "other/a.md"})
        doc_b = Document(page_content="# Same\nContent.", metadata={"source": "other/b.md"})
        result = deduplicate_documents([doc_a, doc_b])
        assert len(result) == 1
        assert result[0].metadata["source"] == "other/a.md"

    def test_duplicate_prefers_docs_user_path(self) -> None:
        """When a docs/user/ path collides with another, the docs/user/ variant wins."""
        doc_other = Document(page_content="# Same\nContent.", metadata={"source": "other/page.md"})
        doc_user = Document(page_content="# Same\nContent.", metadata={"source": "docs/user/page.md"})
        result = deduplicate_documents([doc_other, doc_user])
        assert len(result) == 1
        assert result[0].metadata["source"] == "docs/user/page.md"

    def test_duplicate_user_first_stays(self) -> None:
        """When docs/user/ path appears first, it is kept and the other dropped."""
        doc_user = Document(page_content="# Same\nContent.", metadata={"source": "docs/user/page.md"})
        doc_other = Document(page_content="# Same\nContent.", metadata={"source": "other/page.md"})
        result = deduplicate_documents([doc_user, doc_other])
        assert len(result) == 1
        assert result[0].metadata["source"] == "docs/user/page.md"

    def test_empty_list(self) -> None:
        """An empty list produces an empty result."""
        assert deduplicate_documents([]) == []
