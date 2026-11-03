from unittest.mock import MagicMock, Mock, patch

import pytest
from indexing.adaptive_indexer import (
    HEADER_LEVELS,
    AdaptiveSplitMarkdownIndexer,
    _is_html_table_content,
    encoding,
)
from indexing.html_table_splitter import HtmlTableParser
from indexing.text_utils import (
    extract_first_title,
    remove_braces,
    remove_brackets,
    remove_header_brackets,
    remove_parentheses,
)
from langchain_core.documents import Document

from utils.utils import sanitize_table_name

pytestmark = pytest.mark.unit


@pytest.fixture(scope="session")
def fixtures_path(root_tests_path) -> str:
    return f"{root_tests_path}/unit/fixtures"


@pytest.fixture
def mock_embedding():
    return Mock()


@pytest.fixture
def mock_connection():
    return Mock()


@pytest.fixture
def mock_hana_db():
    with patch("indexing.adaptive_indexer.HanaDB") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def indexer(mock_embedding, mock_connection, mock_hana_db):
    return AdaptiveSplitMarkdownIndexer(
        docs_path="",
        embedding=mock_embedding,
        connection=mock_connection,
        table_name="test_table",
        min_chunk_token_count=1,
        max_chunk_token_count=30,
    )


@pytest.mark.parametrize(
    "input_text,expected",
    [
        ("Hello {world}", "Hello "),
        ("CSS {color: blue}", "CSS "),
        ("No braces here", "No braces here"),
        ("Multiple {first} {second}", "Multiple  "),
        # ("Nested {outer {inner}}", "Nested {outer {inner}}"),  # Nested not supported
        ("{start} middle {end}", " middle "),
    ],
)
def test_remove_braces(input_text: str, expected: str):
    assert remove_braces(input_text) == expected


@pytest.mark.parametrize(
    "input_text,expected",
    [
        ("Python [programming language]", "Python "),
        ("TypeScript [4.0.3]", "TypeScript "),
        ("No brackets here", "No brackets here"),
        ("Multiple [first] [second]", "Multiple  "),
        # ("Nested [outer [inner]]", "Nested [outer [inner]]"),  # Nested not supported
        ("[start] middle [end]", " middle "),
    ],
)
def test_remove_brackets(input_text: str, expected: str):
    assert remove_brackets(input_text) == expected


@pytest.mark.parametrize(
    "input_text,expected",
    [
        ("Hello (world)", "Hello "),
        ("React (JavaScript library)", "React "),
        ("No parentheses here", "No parentheses here"),
        ("Multiple (first) (second)", "Multiple  "),
        # ("Nested (outer (inner))", "Nested (outer (inner))"),  # Nested not supported
        ("(start) middle (end)", " middle "),
    ],
)
def test_remove_parentheses(input_text: str, expected: str):
    assert remove_parentheses(input_text) == expected


@pytest.mark.parametrize(
    "input_text,expected",
    [
        # Test all types of brackets
        ("", ""),
        ("function()", "function()"),  # Empty brackets preserved
        ("Title (with note)", "Title "),
        ("Header [with version]", "Header "),
        ("Component {with props}", "Component "),
        # Test multiple brackets
        ("React (JS) [v18] {props}", "React   "),
        # Test with spaces
        ("Title ( with spaces )", "Title "),
        # Test empty string
        ("", ""),
        # Test no brackets
        ("Plain text", "Plain text"),
        # Test multiple iterations needed
        ("Outer (Inner [nested] content)", "Outer "),
        ("test(test[test[test{test[test]}]])", "test"),
        ("(![adasdas])", ""),
        ("[aaaa](sdas[]dsad),(),(sadasdasd)", "(sdas[]dsad),(),"),
    ],
)
def test_remove_header_brackets(input_text: str, expected: str):
    assert remove_header_brackets(input_text) == expected


@pytest.mark.parametrize(
    "given_text,wanted_title",
    [
        ("# Title 1\nContent 1 ## Subtitle 1\n\n Subcontent 1", "Title 1"),
        ("## Subtitle 1\n\n Subcontent 1 ### Subsubtitle 1", "Subtitle 1"),
        ("### Subsubtitle 1\nSubsubcontent 1", "Subsubtitle 1"),
        ("#### Subsubsubtitle 1\nSubsubsubcontent 1", "Subsubsubtitle 1"),
        ("No title here", None),
        ("", None),
        ("# Title with # in middle\nContent", "Title with # in middle"),
        ("#Invalid title", None),  # No space after #
        ("  # Title with leading spaces\nContent", "Title with leading spaces"),
        ("# Title with trailing spaces  \nContent", "Title with trailing spaces"),
        ("# Multiple\n# Headers\n", "Multiple"),  # Takes first header
    ],
)
def test_extract_first_title(given_text: str, wanted_title: str | None):
    assert extract_first_title(given_text) == wanted_title


@pytest.mark.parametrize(
    "input_name,expected",
    [
        ("kyma_docs", "kyma_docs"),  # already valid
        ("release-0.5.2_e2e", "release_0_5_2_e2e"),  # dots and hyphens replaced
        ("kc_pr_release_0.5.2_e2e", "kc_pr_release_0_5_2_e2e"),  # original error case
        ("my table/name", "my_table_name"),  # spaces and slashes
        ("123starts_with_digit", "_123starts_with_digit"),  # leading digit prefixed
        ("valid_NAME_123", "valid_NAME_123"),  # already valid with mixed case
        ("a!b@c#d", "a_b_c_d"),  # special chars replaced
        ("", ""),  # empty string
    ],
)
def test_sanitize_table_name(input_name: str, expected: str):
    assert sanitize_table_name(input_name) == expected


class TestAdaptiveSplitMarkdownIndexer:
    @pytest.mark.parametrize(
        "given_docs,wanted_results",
        [
            # Test case 1: Document without title (preamble) -- filename used as title.
            # source="test.md" is a bare path; build_chunk_metadata strips a module prefix
            # so path becomes "" and the fallback title is "unknown".
            (
                [
                    Document(
                        page_content="Some content without a title",
                        metadata={"source": "test.md"},
                    )
                ],
                [
                    {
                        "content": "# unknown\n\nSome content without a title",
                        "metadata": {"module": "test.md"},
                        "expected_chunks": 1,
                    }
                ],
            ),
            # Test case 2: Document whose first line heading does NOT match the title —
            # the heading must NOT be stripped (Fix 5: only strip when heading == title).
            (
                [
                    Document(
                        page_content="# Existing Header\nSome content",
                        metadata={"title": "New Title", "source": "test.md"},
                    )
                ],
                [
                    {
                        "content": "# New Title\n\n# Existing Header\nSome content",
                        "metadata": {"title": "New Title"},
                        "expected_chunks": 1,
                    }
                ],
            ),
            (
                [
                    Document(
                        page_content="# Existing Header\n\n\nSome content",
                        metadata={"title": "New Title", "source": "test.md"},
                    )
                ],
                [
                    {
                        "content": "# New Title\n\n# Existing Header\n\n\nSome content",
                        "metadata": {"title": "New Title"},
                        "expected_chunks": 1,
                    }
                ],
            ),
            # Test case 3: Document whose first line heading exactly matches the title —
            # the duplicate heading is stripped.
            (
                [
                    Document(
                        page_content="# Main Header - Sub Header\n\nSome content\n\n## Sub Header\n\nMore content",
                        metadata={
                            "title": "Main Header - Sub Header",
                            "source": "test.md",
                        },
                    )
                ],
                [
                    {
                        "content": "# Main Header - Sub Header\n\nSome content\n\n## Sub Header\n\nMore content",
                        "metadata": {
                            "title": "Main Header - Sub Header",
                        },
                        "expected_chunks": 1,
                    }
                ],
            ),
            # Test case 4: Multiple documents for counter testing
            (
                [
                    Document(page_content="Doc 1", metadata={"source": "test1.md"}),
                    Document(page_content="Doc 2", metadata={"source": "test2.md"}),
                    Document(page_content="Doc 3", metadata={"source": "test3.md"}),
                ],
                [{"expected_chunks": 3}],
            ),
        ],
    )
    def test_process_document_titles(self, given_docs, wanted_results, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=1000,
        )

        processed_docs = list(indexer.process_document_titles(given_docs))

        for i, expected in enumerate(wanted_results):
            if "expected_chunks" in expected:
                assert len(processed_docs) == expected["expected_chunks"]

            if i >= len(processed_docs):
                continue

            if "content" in expected:
                assert processed_docs[i].page_content == expected["content"]

            if "content_startswith" in expected:
                assert processed_docs[i].page_content.startswith(expected["content_startswith"])

            if "content_contains" in expected:
                for content in expected["content_contains"]:
                    assert content in processed_docs[i].page_content

            if "metadata" in expected:
                for key, value in expected["metadata"].items():
                    assert processed_docs[i].metadata[key] == value

    @pytest.mark.parametrize(
        "given_docs,wanted_results",
        [
            (
                # single doc: not chunked as token count is smaller than min_chunk_token_count
                [
                    Document(
                        page_content=(
                            "# Title\n"
                            "Title content\n\n"
                            "## Subtitle\n"
                            "Subtitle content\n\n"
                            "### Subsubtitle\n"
                            "Subsubtitle content\n\n"
                            "#### Subsubsubtitle\n"
                            "Subsubsubtitle content"
                        ),
                        metadata={
                            "source": "test1.md",
                        },
                    ),
                ],
                [
                    Document(
                        page_content=(
                            "# Title\n"
                            "Title content\n\n"
                            "## Subtitle\n"
                            "Subtitle content\n\n"
                            "### Subsubtitle\n"
                            "Subsubtitle content\n\n"
                            "#### Subsubsubtitle\n"
                            "Subsubsubtitle content"
                        ),
                        metadata={
                            "module": "test1.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test1.md",
                            "title": "Title",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title",
                        },
                    ),
                ],
            ),
            (
                # single doc: chunk til H2 (##) header level
                [
                    Document(
                        page_content=(
                            "# Title 1\n"
                            "Title content for testing ...\n\n"
                            "## Subtitle 1\n"
                            "Subtitle content for testing ...\n\n"
                            "### Subsubtitle 1\n"
                            "Subsubtitle conten\n\n"
                            "# Title 2\n"
                            "Title2 content for testing ...\n\n"
                            "## Subtitle 2\n"
                            "Subtitle2 content for testing ...\n\n"
                            "### Subsubtitle 2\n"
                            "Subsubtitle2 content for testing ...\n\n"
                        ),
                        metadata={"source": "test2.md"},
                    ),
                ],
                [
                    Document(
                        page_content="# Title 1\nTitle content for testing ...",
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 1",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title 1",
                        },
                    ),
                    Document(
                        page_content=(
                            "## Subtitle 1\nSubtitle content for testing ...\n### Subsubtitle 1\nSubsubtitle conten"
                        ),
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 1 - Subtitle 1",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subtitle 1",
                        },
                    ),
                    Document(
                        page_content="# Title 2\nTitle2 content for testing ...",
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 2",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title 2",
                        },
                    ),
                    Document(
                        page_content=(
                            "## Subtitle 2\n"
                            "Subtitle2 content for testing ...\n"
                            "### Subsubtitle 2\n"
                            "Subsubtitle2 content for testing ..."
                        ),
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 2 - Subtitle 2",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subtitle 2",
                        },
                    ),
                ],
            ),
            (
                # single doc: chunk til H3 (###) header level
                [
                    Document(
                        page_content=(
                            "# Title 1\n"
                            "Title content for testing ...\n\n"
                            "## Subtitle 1\n"
                            "Subtitle content for testing ...\n\n"
                            "### Subsubtitle 1\n"
                            "Subsubtitle content for testing ...\n\n"
                            "#### Subsubsubtitle 1\n"
                            "Subsubsubtitle content for testing ...\n\n"
                            "# Title 2\n"
                            "Title2 content for testing ...\n\n"
                            "## Subtitle 2\n"
                            "Subtitle2 content for testing ...\n\n"
                            "### Subsubtitle 2\n"
                            "Subsubtitle2 content for testing ...\n\n"
                            "#### Subsubsubtitle 2\n"
                            "Subsubsubtitle2 content for testing ...\n\n"
                            "# Title 3\n"
                            "Title3 content for testing ...\n\n"
                            "## Subtitle 3\n"
                            "Subtitle3 content for testing ...\n\n"
                            "### Subsubtitle 3\n"
                            "Subsubtitle3 content for testing ...\n\n"
                            "#### Subsubsubtitle 3\n"
                            "Subsubsubtitle3 content for testing ..."
                        ),
                        metadata={"source": "test3.md"},
                    ),
                ],
                [
                    Document(
                        page_content="# Title 1\nTitle content for testing ...",
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 1",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title 1",
                        },
                    ),
                    Document(
                        page_content=("## Subtitle 1\nSubtitle content for testing ..."),
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 1 - Subtitle 1",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subtitle 1",
                        },
                    ),
                    Document(
                        page_content=(
                            "### Subsubtitle 1\n"
                            "Subsubtitle content for testing ...\n"  # why '\n\n' not kept?
                            "#### Subsubsubtitle 1\n"
                            "Subsubsubtitle content for testing ..."
                        ),
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 1 - Subtitle 1 - Subsubtitle 1",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subsubtitle 1",
                        },
                    ),
                    Document(
                        page_content="# Title 2\nTitle2 content for testing ...",
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 2",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title 2",
                        },
                    ),
                    Document(
                        page_content="## Subtitle 2\nSubtitle2 content for testing ...",
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 2 - Subtitle 2",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subtitle 2",
                        },
                    ),
                    Document(
                        page_content=(
                            "### Subsubtitle 2\n"
                            "Subsubtitle2 content for testing ...\n"  # why '\n\n' not kept?
                            "#### Subsubsubtitle 2\n"
                            "Subsubsubtitle2 content for testing ..."
                        ),
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 2 - Subtitle 2 - Subsubtitle 2",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subsubtitle 2",
                        },
                    ),
                    Document(
                        page_content="# Title 3\nTitle3 content for testing ...",
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 3",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title 3",
                        },
                    ),
                    Document(
                        page_content="## Subtitle 3\nSubtitle3 content for testing ...",
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 3 - Subtitle 3",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subtitle 3",
                        },
                    ),
                    Document(
                        page_content=(
                            "### Subsubtitle 3\n"
                            "Subsubtitle3 content for testing ...\n"  # why '\n\n' not kept?
                            "#### Subsubsubtitle 3\n"
                            "Subsubsubtitle3 content for testing ..."
                        ),
                        metadata={
                            "module": "test3.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test3.md",
                            "title": "Title 3 - Subtitle 3 - Subsubtitle 3",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subsubtitle 3",
                        },
                    ),
                ],
            ),
            (
                # multiple docs
                [
                    Document(
                        page_content=(
                            "# Title\n"
                            "Title content\n\n"
                            "## Subtitle\n"
                            "Subtitle content\n\n"
                            "### Subsubtitle\n"
                            "Subsubtitle content\n\n"
                            "#### Subsubsubtitle\n"
                            "Subsubsubtitle content"
                        ),
                        metadata={
                            "source": "test1.md",
                        },
                    ),
                    Document(
                        page_content=(
                            "# Title 1\n"
                            "Title content for testing ...\n\n"
                            "## Subtitle 1\n"
                            "Subtitle content for testing ...\n\n"
                            "### Subsubtitle 1\n"
                            "Subsubtitle content for testing ...\n\n"
                            "#### Subsubsubtitle 1\n"
                            "Subsubsubtitle content for testing ...\n\n"
                            "# Title 2\n"
                            "Title2 content for testing ...\n\n"
                            "## Subtitle 2\n"
                            "Subtitle2 content for testing ...\n\n"
                            "### Subsubtitle 2\n"
                            "Subsubtitle2 content for testing ...\n\n"
                            "#### Subsubsubtitle 2\n"
                            "Subsubsubtitle2 content for testing ..."
                        ),
                        metadata={"source": "test2.md"},
                    ),
                ],
                [
                    Document(
                        page_content=(
                            "# Title\n"
                            "Title content\n\n"
                            "## Subtitle\n"
                            "Subtitle content\n\n"
                            "### Subsubtitle\n"
                            "Subsubtitle content\n\n"
                            "#### Subsubsubtitle\n"
                            "Subsubsubtitle content"
                        ),
                        metadata={
                            "module": "test1.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test1.md",
                            "title": "Title",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title",
                        },
                    ),
                    Document(
                        page_content="# Title 1\nTitle content for testing ...",
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 1",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title 1",
                        },
                    ),
                    Document(
                        page_content=("## Subtitle 1\nSubtitle content for testing ..."),
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 1 - Subtitle 1",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subtitle 1",
                        },
                    ),
                    Document(
                        page_content=(
                            "### Subsubtitle 1\n"
                            "Subsubtitle content for testing ...\n"  # why '\n\n' not kept?
                            "#### Subsubsubtitle 1\n"
                            "Subsubsubtitle content for testing ..."
                        ),
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 1 - Subtitle 1 - Subsubtitle 1",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subsubtitle 1",
                        },
                    ),
                    Document(
                        page_content="# Title 2\nTitle2 content for testing ...",
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 2",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Title 2",
                        },
                    ),
                    Document(
                        page_content="## Subtitle 2\nSubtitle2 content for testing ...",
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 2 - Subtitle 2",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subtitle 2",
                        },
                    ),
                    Document(
                        page_content=(
                            "### Subsubtitle 2\n"
                            "Subsubtitle2 content for testing ...\n"  # why '\n\n' not kept?
                            "#### Subsubsubtitle 2\n"
                            "Subsubsubtitle2 content for testing ..."
                        ),
                        metadata={
                            "module": "test2.md",
                            "path": "",
                            "repo": None,
                            "commit": None,
                            "url": "test2.md",
                            "title": "Title 2 - Subtitle 2 - Subsubtitle 2",
                            "doc_type": None,
                            "audience": ["public"],
                            "heading": "Subsubtitle 2",
                        },
                    ),
                ],
            ),
        ],
    )
    def test_get_document_chunks(self, indexer, given_docs, wanted_results):
        # When
        chunks = list(indexer.get_document_chunks(given_docs))

        # Then:
        # Compare the actual chunks with expected results
        assert chunks == wanted_results

    def test_get_document_chunks_with_code_block(self, mock_embedding, mock_connection, mock_hana_db):
        """H3-level chunk containing a code block (62 tokens) is yielded as-is when max >= 62."""
        # Uses a higher max_chunk_token_count so the 62-token H3 chunk is within limits.
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=100,
        )
        given_docs = [
            Document(
                page_content=(
                    "# Title 1\n"
                    "Title 1 content for testing ...\n\n"
                    "## Subtitle 1\n"
                    "Subtitle 1 content for testing ...\n"
                    "Run the following command:\n"
                    "$ kubectl get pods # this lists the pods in the cluster\n"
                    "### Subsubtitle 1\n"
                    "Subsubtitle 1 content for testing:\n"
                    "Here is the the hello world Python code:\n"
                    "```python\n"
                    "print('Hello, World!') # prints 'Hello, World!' to the console\n"
                    "```\n\n"
                    "#### Subsubsubtitle 1\n"
                    "Subsubsubtitle 1 content for testing ...\n\n"
                    "## Subtitle 2\n"
                    "Subtitle 2 content for testing ..."
                ),
                metadata={"source": "test4.md"},
            ),
        ]
        wanted_results = [
            Document(
                page_content="# Title 1\nTitle 1 content for testing ...",
                metadata={
                    "module": "test4.md",
                    "path": "",
                    "repo": None,
                    "commit": None,
                    "url": "test4.md",
                    "title": "Title 1",
                    "doc_type": None,
                    "audience": ["public"],
                    "heading": "Title 1",
                },
            ),
            Document(
                page_content=(
                    "## Subtitle 1\n"
                    "Subtitle 1 content for testing ...\n"
                    "Run the following command:\n"
                    "$ kubectl get pods # this lists the pods in the cluster\n"
                    "### Subsubtitle 1\n"
                    "Subsubtitle 1 content for testing:\n"
                    "Here is the the hello world Python code:\n"
                    "```python\n"
                    "print('Hello, World!') # prints 'Hello, World!' to the console\n"
                    "```\n"
                    "#### Subsubsubtitle 1\n"
                    "Subsubsubtitle 1 content for testing ..."
                ),
                metadata={
                    "module": "test4.md",
                    "path": "",
                    "repo": None,
                    "commit": None,
                    "url": "test4.md",
                    "title": "Title 1 - Subtitle 1",
                    "doc_type": None,
                    "audience": ["public"],
                    "heading": "Subtitle 1",
                },
            ),
            Document(
                page_content="## Subtitle 2\nSubtitle 2 content for testing ...",
                metadata={
                    "module": "test4.md",
                    "path": "",
                    "repo": None,
                    "commit": None,
                    "url": "test4.md",
                    "title": "Title 1 - Subtitle 2",
                    "doc_type": None,
                    "audience": ["public"],
                    "heading": "Subtitle 2",
                },
            ),
        ]

        chunks = list(indexer.get_document_chunks(given_docs))
        assert chunks == wanted_results


class TestPreambleChunk:
    """Chunks without any Markdown heading (preamble) get a filename-derived title."""

    def test_preamble_gets_filename_title(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="/app/docs",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=1000,
        )
        # Content with no Markdown headings -- a pure preamble.
        doc = Document(
            page_content="This module manages eventing in Kyma. It handles subscriptions and event delivery.",
            metadata={"source": "/app/docs/eventing-manager/README.md"},
        )

        chunks = list(indexer.get_document_chunks([doc]))

        assert len(chunks) == 1
        assert chunks[0].metadata["title"] == "README"
        assert chunks[0].metadata["heading"] == "README"

    def test_preamble_in_large_file_is_not_dropped(self, mock_embedding, mock_connection, mock_hana_db):
        # A file large enough to be split (exceeds max_chunk_token_count=30) but with
        # preamble text before the first heading. The preamble must not be silently dropped.
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="/app/docs",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=30,
        )
        doc = Document(
            page_content=(
                "This is the preamble before any heading. It contains important introductory text.\n\n"
                "# Section One\n\nThis section has enough content to push the document over the token limit.\n\n"
                "# Section Two\n\nMore content here to ensure splitting occurs at the header level.\n\n"
            ),
            metadata={"source": "/app/docs/eventing-manager/overview.md"},
        )

        chunks = list(indexer.get_document_chunks([doc]))

        titles = [c.metadata["title"] for c in chunks]
        assert "overview" in titles, f"preamble chunk missing; got titles: {titles}"

    def test_oversized_preamble_gets_filename_title(self, mock_embedding, mock_connection, mock_hana_db):
        """An oversized preamble (no heading, exceeds token limit) must carry the
        filename-derived title so process_document_titles does not prepend '# '."""
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=10,
        )
        prose = " ".join(["word"] * 50)
        doc = Document(page_content=prose, metadata={"source": "my-doc.md"})
        base_metadata = {"path": "my-doc.md", "module": "my-doc.md"}

        chunks = list(indexer._process_doc(doc, level=len(HEADER_LEVELS), base_metadata=base_metadata))

        assert chunks, "expected at least one chunk"
        for chunk in chunks:
            assert chunk.metadata.get("title") == "my-doc", (
                f"expected 'my-doc' title, got {chunk.metadata.get('title')!r}"
            )


class TestHtmlTableParser:
    """Direct tests for HtmlTableParser — parsing logic independent of the splitter."""

    def test_extracts_intro_header_rows_outro(self):
        html = (
            "Intro text here.\n"
            "<table>\n"
            "<tr><th>Region</th><th>Provider</th></tr>\n"
            "<tr><td>eu-west-1</td><td>AWS</td></tr>\n"
            "<tr><td>us-east-1</td><td>AWS</td></tr>\n"
            "</table>\n"
            "Outro text here."
        )
        parser = HtmlTableParser()
        parser.feed(html)
        parser.close()

        assert parser.outro_text == "Outro text here."
        assert len(parser.tables) == 1
        intro, header_cells, data_rows = parser.tables[0]
        assert intro == "Intro text here."
        assert header_cells == ["Region", "Provider"]
        assert data_rows == [["eu-west-1", "AWS"], ["us-east-1", "AWS"]]

    def test_nested_table_treated_as_cell_content(self):
        html = (
            "<table>\n"
            "<tr><th>Name</th><th>Details</th></tr>\n"
            "<tr><td>Item</td><td><table><tr><td>nested</td></tr></table></td></tr>\n"
            "</table>"
        )
        parser = HtmlTableParser()
        parser.feed(html)
        parser.close()

        assert len(parser.tables) == 1
        _, _header_cells, data_rows = parser.tables[0]  # (intro, header_cells, data_rows)
        assert len(data_rows) == 1  # one outer row, not two

    def test_multiple_tables(self):
        html = (
            "Before.\n"
            "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>\n"
            "Between.\n"
            "<table><tr><th>B</th></tr><tr><td>2</td></tr></table>\n"
            "After."
        )
        parser = HtmlTableParser()
        parser.feed(html)
        parser.close()

        assert len(parser.tables) == 2  # noqa: PLR2004
        assert parser.tables[0][0] == "Before."  # intro of first table
        assert parser.tables[0][1] == ["A"]  # header_cells of first table
        assert parser.tables[1][1] == ["B"]  # header_cells of second table
        assert parser.outro_text == "After."

    def test_no_th_returns_empty_header(self):
        html = "<table><tr><td>val1</td><td>val2</td></tr></table>"
        parser = HtmlTableParser()
        parser.feed(html)
        parser.close()

        _, header_cells, data_rows = parser.tables[0]
        assert header_cells == []
        assert data_rows == [["val1", "val2"]]


class TestIsHtmlTableContent:
    """Unit tests for the _is_html_table_content helper."""

    def test_plain_prose_returns_false(self):
        assert not _is_html_table_content("Just some plain text.\nNo tables here.", 0.2)

    def test_table_heavy_content_returns_true(self):
        html = (
            "<table>\n"
            "<tr><th>Region</th><th>Provider</th></tr>\n"
            "<tr><td>eu-west-1</td><td>AWS</td></tr>\n"
            "<tr><td>us-east-1</td><td>AWS</td></tr>\n"
            "</table>"
        )
        assert _is_html_table_content(html, 0.2)

    def test_fenced_code_block_html_excluded(self):
        # HTML table tags inside a fenced code block must NOT count toward the threshold.
        content = (
            "This document shows an HTML example:\n\n"
            "```html\n"
            "<table>\n"
            "<tr><th>Col</th></tr>\n"
            "<tr><td>val</td></tr>\n"
            "</table>\n"
            "```\n\n"
            "That was just an example snippet."
        )
        assert not _is_html_table_content(content, 0.2)

    def test_mixed_fenced_and_real_table(self):
        # One real table plus one fenced-code example; only real table lines should count.
        content = (
            "Real table below:\n"
            "<table>\n"
            "<tr><th>A</th></tr>\n"
            "<tr><td>1</td></tr>\n"
            "<tr><td>2</td></tr>\n"
            "<tr><td>3</td></tr>\n"
            "<tr><td>4</td></tr>\n"
            "<tr><td>5</td></tr>\n"
            "</table>\n"
            "Example:\n"
            "```html\n"
            "<table><tr><td>ignore</td></tr></table>\n"
            "```"
        )
        assert _is_html_table_content(content, 0.2)

    def test_exactly_at_threshold_returns_false(self):
        # 1 html-tag line out of 5 total = 0.20, which is NOT strictly > threshold.
        content = "line1\nline2\nline3\nline4\n<tr><td>x</td></tr>"
        assert not _is_html_table_content(content, 0.2)


class TestOversizedChunkSplitting:
    """_process_doc routes oversized terminal chunks to _split_oversized."""

    def test_oversized_terminal_calls_split_oversized(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=5,
        )
        doc = Document(
            page_content="### Section\nThis sentence has more than five tokens total.",
            metadata={"title": "Section", "_leaf_header": "Section"},
        )
        with patch.object(indexer, "_split_oversized", return_value=iter([])) as mock_split:
            list(indexer._process_doc(doc, level=len(HEADER_LEVELS), base_metadata={}))
            mock_split.assert_called_once_with(doc, {})

    def test_split_markdown_produces_chunks_within_limit(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=20,
        )
        # ~60 tokens of prose — exceeds limit of 20
        long_prose = (
            "This is the first paragraph with enough words to exceed twenty tokens easily.\n\n"
            "This is the second paragraph which also has plenty of words to fill up tokens.\n\n"
            "This is the third paragraph continuing the pattern of having sufficient content."
        )
        doc = Document(
            page_content=long_prose,
            metadata={"title": "My Section", "_leaf_header": "My Section"},
        )
        chunks = list(indexer._split_markdown(doc, base_metadata={"title": "My Section"}))

        assert len(chunks) > 1
        for chunk in chunks:
            token_count = len(encoding.encode(chunk.page_content))
            assert token_count <= indexer.max_chunk_token_count, f"chunk exceeds limit: {token_count} tokens"

    def test_split_markdown_inherits_metadata(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=20,
        )
        long_prose = (
            "This is the first paragraph with enough words to exceed twenty tokens easily.\n\n"
            "This is the second paragraph which also has plenty of words to fill up tokens."
        )
        doc = Document(
            page_content=long_prose,
            metadata={"title": "My Section", "_leaf_header": "My Section"},
        )
        base = {
            "module": "test.md",
            "path": "",
            "repo": None,
            "commit": None,
            "url": "test.md",
            "title": "My Section",
            "doc_type": None,
            "audience": ["public"],
        }
        chunks = list(indexer._split_markdown(doc, base_metadata=base))

        for chunk in chunks:
            assert chunk.metadata["title"] == "My Section"
            assert chunk.metadata["_leaf_header"] == "My Section"

    def test_split_html_table_intro_header_outro_in_every_chunk(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=30,
        )
        # Build a table with enough rows to force multiple chunks at limit=30
        rows = "\n".join(f"<tr><td>region-{i}</td><td>Provider-{i}</td><td>us-east-{i}</td></tr>" for i in range(15))
        html = (
            "Pick a region.\n"
            "<table>\n"
            "<tr><th>Region</th><th>Provider</th><th>Key</th></tr>\n"
            f"{rows}\n"
            "</table>\n"
            "See docs for details."
        )
        doc = Document(
            page_content=html,
            metadata={"title": "Regions", "_leaf_header": "Regions"},
        )
        chunks = list(indexer._split_html_table(doc, base_metadata={"title": "Regions", "_leaf_header": "Regions"}))

        assert len(chunks) > 1
        for chunk in chunks:
            assert "Pick a region." in chunk.page_content  # intro
            assert "Region" in chunk.page_content  # header row
            assert "Provider" in chunk.page_content  # header row
            assert "See docs for details." in chunk.page_content  # outro

    def test_split_html_table_inherits_metadata(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=30,
        )
        rows = "\n".join(f"<tr><td>region-{i}</td><td>Provider-{i}</td></tr>" for i in range(15))
        html = f"<table><tr><th>Region</th><th>Provider</th></tr>{rows}</table>"
        doc = Document(
            page_content=html,
            metadata={"title": "Regions", "_leaf_header": "Regions"},
        )
        base = {
            "module": "test.md",
            "path": "",
            "repo": None,
            "commit": None,
            "url": "test.md",
            "title": "Regions",
            "doc_type": None,
            "audience": ["public"],
        }
        chunks = list(indexer._split_html_table(doc, base_metadata=base))

        for chunk in chunks:
            assert chunk.metadata["title"] == "Regions"
            assert chunk.metadata["_leaf_header"] == "Regions"

    def test_split_html_table_no_table_falls_through_to_markdown(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=20,
        )
        prose = (
            "This is plain markdown text with no HTML table at all.\n\n"
            "It has multiple paragraphs to ensure it gets split by the markdown splitter.\n\n"
            "Third paragraph to push it over the token limit for testing purposes here."
        )
        doc = Document(
            page_content=prose,
            metadata={"title": "Section", "_leaf_header": "Section"},
        )
        chunks = list(indexer._split_html_table(doc, base_metadata={"title": "Section", "_leaf_header": "Section"}))
        # Falls through to _split_markdown — produces multiple chunks, all within limit
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(encoding.encode(chunk.page_content)) <= indexer.max_chunk_token_count

    def test_split_html_table_no_chunk_exceeds_max(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=30,
        )
        rows = "\n".join(f"<tr><td>region-{i}</td><td>Provider-{i}</td><td>key-{i}</td></tr>" for i in range(20))
        html = (
            "Pick a region.\n"
            "<table>\n"
            "<tr><th>Region</th><th>Provider</th><th>Key</th></tr>\n"
            f"{rows}\n"
            "</table>\n"
            "See docs."
        )
        doc = Document(
            page_content=html,
            metadata={"title": "Regions", "_leaf_header": "Regions"},
        )
        chunks = list(indexer._split_html_table(doc, base_metadata={"title": "Regions", "_leaf_header": "Regions"}))

        assert len(chunks) > 1
        for chunk in chunks:
            tokens = len(encoding.encode(chunk.page_content))
            assert tokens <= indexer.max_chunk_token_count, f"chunk exceeds limit: {tokens} tokens"

    def test_split_html_table_no_th_omits_header_row(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=30,
        )
        rows = "\n".join(f"<tr><td>region-{i}</td><td>Provider-{i}</td></tr>" for i in range(15))
        html = f"<table>{rows}</table>"
        doc = Document(
            page_content=html,
            metadata={"title": "T", "_leaf_header": "T"},
        )
        chunks = list(indexer._split_html_table(doc, base_metadata={"title": "T", "_leaf_header": "T"}))

        # Without <th>, header_row is empty — no header-only line should appear before data
        # The first line of the first chunk content should be a data row (contains "region-0")
        assert "region-0" in chunks[0].page_content
        # Verify multiple chunks were produced (no header tokens inflate the budget)
        assert len(chunks) > 1

    def test_split_html_table_nested_table_at_splitter_level(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=100,
        )
        html = (
            "<table>\n"
            "<tr><th>Name</th><th>Details</th></tr>\n"
            "<tr><td>Item A</td><td><table><tr><td>nested data</td></tr></table></td></tr>\n"
            "<tr><td>Item B</td><td>simple data</td></tr>\n"
            "</table>"
        )
        doc = Document(
            page_content=html,
            metadata={"title": "T", "_leaf_header": "T"},
        )
        chunks = list(indexer._split_html_table(doc, base_metadata={"title": "T", "_leaf_header": "T"}))

        # Should produce at least one chunk (may be just one if it fits)
        assert len(chunks) >= 1
        # The nested table should NOT create an extra table split
        # All data should be in the chunks
        combined = "\n".join(c.page_content for c in chunks)
        assert "Name" in combined  # header row
        assert "Item A" in combined
        assert "Item B" in combined

    def test_split_html_table_multiple_tables_at_splitter_level(self, mock_embedding, mock_connection, mock_hana_db):
        """Two tables: intro belongs to its own table; outro only on the last table.

        Layout: <table_a> "Between text." <table_b> "After text."
        - table_a chunks: intro="", outro="" (Between text. is table_b's intro)
        - table_b chunks: intro="Between text.", outro="After text."
        """
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=30,
        )
        rows_a = "\n".join(f"<tr><td>a-{i}</td></tr>" for i in range(10))
        rows_b = "\n".join(f"<tr><td>b-{i}</td></tr>" for i in range(10))
        html = (
            f"<table><tr><th>ColA</th></tr>{rows_a}</table>\n"
            "Between text.\n"
            f"<table><tr><th>ColB</th></tr>{rows_b}</table>\n"
            "After text."
        )
        doc = Document(
            page_content=html,
            metadata={"title": "T", "_leaf_header": "T"},
        )
        chunks = list(indexer._split_html_table(doc, base_metadata={"title": "T", "_leaf_header": "T"}))

        table_a_chunks = [c for c in chunks if "ColA" in c.page_content]
        table_b_chunks = [c for c in chunks if "ColB" in c.page_content]

        assert table_a_chunks, "expected chunks from table A"
        assert table_b_chunks, "expected chunks from table B"

        # table_a: Between text. must NOT appear (it is table_b's intro)
        for chunk in table_a_chunks:
            assert "Between text." not in chunk.page_content
            assert "After text." not in chunk.page_content

        # table_b: Between text. is the intro; After text. is the outro
        for chunk in table_b_chunks:
            assert "Between text." in chunk.page_content
            assert "After text." in chunk.page_content

    def test_split_html_table_header_only_table_emits_chunk(self, mock_embedding, mock_connection, mock_hana_db):
        """A table with header row but no data rows must not silently drop its content."""
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=100,
        )
        html = "Intro text.\n<table><tr><th>Col A</th><th>Col B</th></tr></table>\nOutro text."
        doc = Document(page_content=html, metadata={"title": "T", "_leaf_header": "T"})
        chunks = list(indexer._split_html_table(doc, base_metadata={"title": "T", "_leaf_header": "T"}))

        assert len(chunks) == 1
        assert "Intro text." in chunks[0].page_content
        assert "Col A" in chunks[0].page_content
        assert "Outro text." in chunks[0].page_content

    def test_split_oversized_routes_html_to_table_splitter(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=30,
        )
        rows = "\n".join(f"<tr><td>r{i}</td><td>p{i}</td></tr>" for i in range(20))
        html = f"Intro.\n<table><tr><th>R</th><th>P</th></tr>{rows}</table>\nOutro."
        doc = Document(
            page_content=html,
            metadata={"title": "T", "_leaf_header": "T"},
        )
        with patch.object(indexer, "_split_html_table", wraps=indexer._split_html_table) as mock_html:
            list(indexer._split_oversized(doc, {"title": "T", "_leaf_header": "T"}))
            mock_html.assert_called_once()

    def test_split_oversized_routes_prose_to_markdown_splitter(self, mock_embedding, mock_connection, mock_hana_db):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=20,
        )
        prose = (
            "First paragraph with enough tokens to be oversized here.\n\n"
            "Second paragraph also contributing tokens to this oversized document text."
        )
        doc = Document(page_content=prose, metadata={"title": "T", "_leaf_header": "T"})
        with patch.object(indexer, "_split_markdown", wraps=indexer._split_markdown) as mock_md:
            list(indexer._split_oversized(doc, {"title": "T", "_leaf_header": "T"}))
            mock_md.assert_called_once()

    def test_end_to_end_html_table_at_h3_terminal(self, mock_embedding, mock_connection, mock_hana_db):
        """A doc whose H2 section contains only an HTML table (no H3) produces
        multiple bounded chunks, each with correct title metadata and
        intro/header/outro content repeated."""
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=40,
        )
        rows = "\n".join(f"<tr><td>region-{i:02d}</td><td>Provider</td><td>key-{i:02d}</td></tr>" for i in range(20))
        html_section = (
            "# Regions for Kyma\n\n"
            "## Subaccount Regions\n\n"
            "Pick a subaccount region.\n\n"
            "<table>\n"
            "<tr><th>Region</th><th>Provider</th><th>Key</th></tr>\n"
            f"{rows}\n"
            "</table>\n\n"
            "See cluster regions for more."
        )
        doc = Document(page_content=html_section, metadata={"source": "regions.md"})

        chunks = list(indexer.get_document_chunks([doc]))

        # All chunks must carry the section title
        for chunk in chunks:
            assert chunk.metadata.get("title"), "chunk missing title"
            assert "chunk_index" not in chunk.metadata
            assert "total_chunks" not in chunk.metadata

    def test_end_to_end_process_document_titles_adds_title_header(self, mock_embedding, mock_connection, mock_hana_db):
        """process_document_titles must prepend # title to every sub-chunk."""
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=1,
            max_chunk_token_count=40,
        )
        rows = "\n".join(f"<tr><td>region-{i:02d}</td><td>Provider</td><td>key-{i:02d}</td></tr>" for i in range(20))
        html_section = (
            "# Regions\n\n"
            "## Subaccount Regions\n\n"
            "Pick a region.\n\n"
            "<table>\n"
            "<tr><th>Region</th><th>Provider</th><th>Key</th></tr>\n"
            f"{rows}\n"
            "</table>\n\n"
            "See more."
        )
        doc = Document(page_content=html_section, metadata={"source": "regions.md"})

        chunks = list(indexer.process_document_titles([doc]))

        for chunk in chunks:
            assert chunk.page_content.startswith("# "), (
                f"chunk does not start with title header: {chunk.page_content[:60]}"
            )

    def test_chunks_below_min_token_count_are_dropped(self, mock_embedding, mock_connection, mock_hana_db):
        """Chunks whose token count is <= min_chunk_token_count must be silently dropped."""
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="test_table",
            min_chunk_token_count=50,
            max_chunk_token_count=1000,
        )
        # Each section is ~5 tokens — well below min_chunk_token_count=50.
        doc = Document(
            page_content="# Title\nShort.\n\n## Sub\nAlso short.\n\n### Sub-sub\nTiny.",
            metadata={"source": "tiny.md"},
        )

        chunks = list(indexer.get_document_chunks([doc]))

        assert chunks == [], f"expected no chunks, got {len(chunks)}: {[c.page_content for c in chunks]}"
