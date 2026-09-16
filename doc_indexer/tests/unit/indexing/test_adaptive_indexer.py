import json
from unittest.mock import MagicMock, Mock, patch

import pytest
import tiktoken
from hdbcli import dbapi
from indexing.adaptive_indexer import (
    AdaptiveSplitMarkdownIndexer,
    extract_first_title,
    remove_braces,
    remove_brackets,
    remove_header_brackets,
    remove_parentheses,
)
from langchain_core.documents import Document
from utils.manifest import load_manifest_documents

from utils.utils import sanitize_table_name

pytestmark = pytest.mark.unit

_encoding = tiktoken.encoding_for_model("gpt-4o")


def _token_count(text: str) -> int:
    return len(_encoding.encode(text))


def _make_words(n: int, word: str = "word") -> str:
    """Return a string of approximately n tokens by repeating `word`."""
    return (word + " ") * n


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
            # Test case 1: Document without title
            (
                [
                    Document(
                        page_content="Some content without a title",
                        metadata={"source": "test.md"},
                    )
                ],
                [
                    {
                        "content": "Some content without a title",
                        "metadata": {"source": "test.md"},
                        "expected_chunks": 0,
                    }
                ],
            ),
            # Test case 2: Document with existing header
            (
                [
                    Document(
                        page_content="# Existing Header\nSome content",
                        metadata={"title": "New Title", "source": "test.md"},
                    )
                ],
                [
                    {
                        "content": "# New Title\nSome content",
                        "metadata": {"title": "New Title", "source": "test.md"},
                        "expected_chunks": 0,
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
                        "content": "# New Title\n\n\nSome content",
                        "metadata": {"title": "New Title", "source": "test.md"},
                        "expected_chunks": 0,
                    }
                ],
            ),
            # Test case 3: Document with hierarchical headers
            (
                [
                    Document(
                        page_content="# Main Header\n\nSome content\n\n## Sub Header\n\nMore content",
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
                            "source": "test.md",
                        },
                        "expected_chunks": 0,
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
                [{"expected_chunks": 2}],
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
                            "source": "test1.md",
                            "title": "Title",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test2.md",
                            "title": "Title 1",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content=(
                            "## Subtitle 1\nSubtitle content for testing ...\n### Subsubtitle 1\nSubsubtitle conten"
                        ),
                        metadata={
                            "source": "test2.md",
                            "title": "Title 1 - Subtitle 1",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="# Title 2\nTitle2 content for testing ...",
                        metadata={
                            "source": "test2.md",
                            "title": "Title 2",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test2.md",
                            "title": "Title 2 - Subtitle 2",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test3.md",
                            "title": "Title 1",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content=("## Subtitle 1\nSubtitle content for testing ..."),
                        metadata={
                            "source": "test3.md",
                            "title": "Title 1 - Subtitle 1",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test3.md",
                            "title": "Title 1 - Subtitle 1 - Subsubtitle 1",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="# Title 2\nTitle2 content for testing ...",
                        metadata={
                            "source": "test3.md",
                            "title": "Title 2",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="## Subtitle 2\nSubtitle2 content for testing ...",
                        metadata={
                            "source": "test3.md",
                            "title": "Title 2 - Subtitle 2",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test3.md",
                            "title": "Title 2 - Subtitle 2 - Subsubtitle 2",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="# Title 3\nTitle3 content for testing ...",
                        metadata={
                            "source": "test3.md",
                            "title": "Title 3",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="## Subtitle 3\nSubtitle3 content for testing ...",
                        metadata={
                            "source": "test3.md",
                            "title": "Title 3 - Subtitle 3",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test3.md",
                            "title": "Title 3 - Subtitle 3 - Subsubtitle 3",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test1.md",
                            "title": "Title",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="# Title 1\nTitle content for testing ...",
                        metadata={
                            "source": "test2.md",
                            "title": "Title 1",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content=("## Subtitle 1\nSubtitle content for testing ..."),
                        metadata={
                            "source": "test2.md",
                            "title": "Title 1 - Subtitle 1",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test2.md",
                            "title": "Title 1 - Subtitle 1 - Subsubtitle 1",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="# Title 2\nTitle2 content for testing ...",
                        metadata={
                            "source": "test2.md",
                            "title": "Title 2",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="## Subtitle 2\nSubtitle2 content for testing ...",
                        metadata={
                            "source": "test2.md",
                            "title": "Title 2 - Subtitle 2",
                            "module": "kyma",
                            "version": "latest",
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
                            "source": "test2.md",
                            "title": "Title 2 - Subtitle 2 - Subsubtitle 2",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                ],
            ),
            (
                # when conent contains #, ## or ###, the chunk is not split
                [
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
                ],
                [
                    Document(
                        page_content="# Title 1\nTitle 1 content for testing ...",
                        metadata={
                            "source": "test4.md",
                            "title": "Title 1",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content=(
                            "## Subtitle 1\n"
                            "Subtitle 1 content for testing ...\n"
                            "Run the following command:\n"
                            "$ kubectl get pods # this lists the pods in the cluster"
                        ),
                        metadata={
                            "source": "test4.md",
                            "title": "Title 1 - Subtitle 1",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content=(
                            "### Subsubtitle 1\n"
                            "Subsubtitle 1 content for testing:\n"
                            "Here is the the hello world Python code:"
                        ),
                        metadata={
                            "source": "test4.md",
                            "title": "Title 1 - Subtitle 1 - Subsubtitle 1 (part 1/3)",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content=(
                            "```python\nprint('Hello, World!') # prints 'Hello, World!' to the console\n```\n"
                        ),
                        metadata={
                            "source": "test4.md",
                            "title": "Title 1 - Subtitle 1 - Subsubtitle 1 (part 2/3)",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content=("#### Subsubsubtitle 1\nSubsubsubtitle 1 content for testing ..."),
                        metadata={
                            "source": "test4.md",
                            "title": "Title 1 - Subtitle 1 - Subsubtitle 1 (part 3/3)",
                            "module": "kyma",
                            "version": "latest",
                        },
                    ),
                    Document(
                        page_content="## Subtitle 2\nSubtitle 2 content for testing ...",
                        metadata={
                            "source": "test4.md",
                            "title": "Title 1 - Subtitle 2",
                            "module": "kyma",
                            "version": "latest",
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


# ---------------------------------------------------------------------------
# Atomic-swap unit tests for AdaptiveSplitMarkdownIndexer.index()
# ---------------------------------------------------------------------------

TABLE_NAME = "test_table"

# One chunk whose token count is above min_chunk_token_count=1.
SAMPLE_DOC = Document(
    page_content="# Title\nSome content that is definitely long enough to survive token filtering.",
    metadata={"source": "test.md"},
)


def _make_mock_cursor(row_count: int) -> MagicMock:
    """Return a mock cursor whose fetchone() returns (row_count,)."""
    cursor = MagicMock()
    cursor.fetchone.return_value = (row_count,)
    # support context-manager use: `with connection.cursor() as cursor`
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = Mock(return_value=False)
    return cursor


@pytest.fixture
def mock_connection_with_cursor():
    """Mock connection whose cursor() always returns a fresh mock cursor."""
    conn = Mock()
    conn.cursor = Mock(return_value=_make_mock_cursor(1))
    return conn


@pytest.fixture
def indexer_for_swap(mock_embedding, mock_connection_with_cursor, mock_hana_db):
    """Indexer wired with a mock connection that can be interrogated for SQL calls."""
    return AdaptiveSplitMarkdownIndexer(
        docs_path="",
        embedding=mock_embedding,
        connection=mock_connection_with_cursor,
        table_name=TABLE_NAME,
        min_chunk_token_count=1,
        max_chunk_token_count=10000,
    )


class TestIndexAtomicSwap:
    """Tests for the staging-table rename-swap logic in AdaptiveSplitMarkdownIndexer.index()."""

    def test_success_swap_sequence(self, indexer_for_swap: AdaptiveSplitMarkdownIndexer) -> None:
        """On success: chunks inserted, count verified, and rename/drop called in order."""
        indexer = indexer_for_swap
        live = indexer.table_name

        with (
            patch("indexing.adaptive_indexer.load_documents", return_value=[SAMPLE_DOC]),
            patch("indexing.adaptive_indexer.INDEX_TO_FILE", False),
            patch("indexing.adaptive_indexer.CHUNKS_BATCH_SIZE", 100),
            patch("time.sleep"),
            patch("indexing.adaptive_indexer.drop_table") as mock_drop,
            patch("indexing.adaptive_indexer.rename_table") as mock_rename,
            patch("indexing.adaptive_indexer.DATABASE_USER", "TESTUSER"),
        ):
            # cursor returns 1 row (matches the 1 chunk that will be inserted)
            indexer.connection.cursor.return_value = _make_mock_cursor(1)

            indexer.index()

        # Capture staging name after index() has set it
        staging = indexer.staging_table_name

        # rename called twice: live->old, staging->live
        expected_rename_count = 2
        assert mock_rename.call_count == expected_rename_count
        first_rename_args = mock_rename.call_args_list[0]
        # First rename: live -> <live>_old_<ts>; assert format not circular
        old_table_arg = first_rename_args[0][3]
        assert old_table_arg.startswith(live), f"Expected old table name to start with '{live}', got '{old_table_arg}'"
        assert "_old_" in old_table_arg, f"Expected '_old_' in old table name, got '{old_table_arg}'"
        assert first_rename_args[1].get("ignore_missing") is True
        second_rename_args = mock_rename.call_args_list[1]
        assert second_rename_args[0][2] == staging
        assert second_rename_args[0][3] == live

        # drop called once for the old table (not for staging, which was swapped in)
        assert mock_drop.call_count == 1
        dropped_name = mock_drop.call_args[0][2]
        assert dropped_name != staging
        assert dropped_name != live

        # add_documents was called at least once
        indexer.db.add_documents.assert_called()

    def test_failure_before_swap_drops_staging(self, indexer_for_swap: AdaptiveSplitMarkdownIndexer) -> None:
        """If add_documents raises, staging table is dropped and live table is untouched."""
        indexer = indexer_for_swap

        with (
            patch("indexing.adaptive_indexer.load_documents", return_value=[SAMPLE_DOC]),
            patch("indexing.adaptive_indexer.INDEX_TO_FILE", False),
            patch("indexing.adaptive_indexer.CHUNKS_BATCH_SIZE", 100),
            patch("time.sleep"),
            patch("indexing.adaptive_indexer.drop_table") as mock_drop,
            patch("indexing.adaptive_indexer.rename_table") as mock_rename,
            patch("indexing.adaptive_indexer.DATABASE_USER", "TESTUSER"),
        ):
            indexer.db.add_documents.side_effect = RuntimeError("insert failed")

            with pytest.raises(RuntimeError, match="insert failed"):
                indexer.index()

        # staging table must be dropped
        assert mock_drop.call_count == 1
        mock_drop.assert_called_once_with(indexer.connection, "TESTUSER", indexer.staging_table_name)
        # live table must NOT be touched (no rename)
        mock_rename.assert_not_called()

    def test_failure_on_second_rename_restores_live(self, indexer_for_swap: AdaptiveSplitMarkdownIndexer) -> None:
        """If the staging->live rename fails, the old live table is renamed back."""
        indexer = indexer_for_swap
        live = indexer.table_name

        rename_error = dbapi.ProgrammingError("rename failed")
        rename_error.errorcode = 999  # not error 259

        call_count = {"n": 0}
        second_rename_call = 2
        expected_total_rename_calls = 3

        def rename_side_effect(
            conn: object,
            db_user: str,
            old: str,
            new: str,
            ignore_missing: bool = False,
        ) -> None:
            call_count["n"] += 1
            if call_count["n"] == second_rename_call:
                # Second call is staging -> live; make it fail
                raise rename_error

        with (
            patch("indexing.adaptive_indexer.load_documents", return_value=[SAMPLE_DOC]),
            patch("indexing.adaptive_indexer.INDEX_TO_FILE", False),
            patch("indexing.adaptive_indexer.CHUNKS_BATCH_SIZE", 100),
            patch("time.sleep"),
            patch("indexing.adaptive_indexer.drop_table") as mock_drop,
            patch("indexing.adaptive_indexer.rename_table", side_effect=rename_side_effect) as mock_rename,
            patch("indexing.adaptive_indexer.DATABASE_USER", "TESTUSER"),
        ):
            indexer.connection.cursor.return_value = _make_mock_cursor(1)

            with pytest.raises(dbapi.ProgrammingError):
                indexer.index()

        # Three rename calls: live->old, staging->live (fails), old->live (restore)
        assert mock_rename.call_count == expected_total_rename_calls
        restore_call = mock_rename.call_args_list[expected_total_rename_calls - 1]
        # Third call: old_table_name -> live
        assert restore_call[0][3] == live

        # drop must NOT have been called (swap never completed)
        mock_drop.assert_not_called()

    def test_row_count_mismatch_drops_staging(self, indexer_for_swap: AdaptiveSplitMarkdownIndexer) -> None:
        """If the staging row count does not match chunks written, staging is dropped."""
        indexer = indexer_for_swap

        with (
            patch("indexing.adaptive_indexer.load_documents", return_value=[SAMPLE_DOC]),
            patch("indexing.adaptive_indexer.INDEX_TO_FILE", False),
            patch("indexing.adaptive_indexer.CHUNKS_BATCH_SIZE", 100),
            patch("time.sleep"),
            patch("indexing.adaptive_indexer.drop_table") as mock_drop,
            patch("indexing.adaptive_indexer.rename_table") as mock_rename,
            patch("indexing.adaptive_indexer.DATABASE_USER", "TESTUSER"),
        ):
            # DB returns fewer rows than written -- distinct from zero-chunk case
            indexer.connection.cursor.return_value = _make_mock_cursor(0)

            with pytest.raises(RuntimeError, match="row count mismatch"):
                indexer.index()

        mock_drop.assert_called_once_with(indexer.connection, "TESTUSER", indexer.staging_table_name)
        mock_rename.assert_not_called()

    def test_empty_docs_drops_staging(self, indexer_for_swap: AdaptiveSplitMarkdownIndexer) -> None:
        """If all documents produce zero chunks, staging is dropped with a distinct error."""
        indexer = indexer_for_swap

        with (
            # SAMPLE_DOC filtered out by min_chunk_token_count via a tiny doc
            patch("indexing.adaptive_indexer.load_documents", return_value=[]),
            patch("indexing.adaptive_indexer.INDEX_TO_FILE", False),
            patch("indexing.adaptive_indexer.CHUNKS_BATCH_SIZE", 100),
            patch("time.sleep"),
            patch("indexing.adaptive_indexer.drop_table") as mock_drop,
            patch("indexing.adaptive_indexer.rename_table") as mock_rename,
            patch("indexing.adaptive_indexer.DATABASE_USER", "TESTUSER"),
        ):
            indexer.connection.cursor.return_value = _make_mock_cursor(0)

            with pytest.raises(RuntimeError, match="No chunks were produced"):
                indexer.index()

        mock_drop.assert_called_once_with(indexer.connection, "TESTUSER", indexer.staging_table_name)
        mock_rename.assert_not_called()


class TestIndexToFileDryRun:
    """INDEX_TO_FILE lets the indexer run without a HANA connection or an embedding model."""

    def test_init_requires_connection_and_embedding_unless_index_to_file(self):
        with (
            patch("indexing.adaptive_indexer.INDEX_TO_FILE", False),
            pytest.raises(ValueError, match="connection and embedding are required"),
        ):
            AdaptiveSplitMarkdownIndexer(docs_path="", embedding=None, connection=None)

    def test_init_allows_none_connection_and_embedding_when_index_to_file(self):
        with patch("indexing.adaptive_indexer.INDEX_TO_FILE", True):
            indexer = AdaptiveSplitMarkdownIndexer(docs_path="", embedding=None, connection=None)

        assert indexer.db is None

    def test_index_writes_file_without_connection_or_embedding(self, tmp_path, monkeypatch):
        """The full index() dry-run path never touches HANA or the embedding model."""
        output_dir = tmp_path
        # index() writes to a relative path (cwd) -- chdir so the test doesn't litter the repo.
        monkeypatch.chdir(output_dir)

        with (
            patch("indexing.adaptive_indexer.INDEX_TO_FILE", True),
            patch("indexing.adaptive_indexer.load_documents", return_value=[SAMPLE_DOC]),
        ):
            indexer = AdaptiveSplitMarkdownIndexer(
                docs_path="",
                embedding=None,
                connection=None,
                table_name=TABLE_NAME,
                min_chunk_token_count=1,
                max_chunk_token_count=10000,
            )
            indexer.index()

        output_files = list(output_dir.glob("Kyma_Documentation_chunks_*.json"))
        assert len(output_files) == 1
        written = json.loads(output_files[0].read_text(encoding="utf-8"))
        assert len(written["kyma_docs"]) == 1
        assert written["kyma_docs"][0]["metadata"]["title"] == "Title"


class TestTinySectionMerging:
    """Tiny sections (<=min_chunk_token_count tokens) must never be dropped."""

    def test_tiny_section_merged_into_previous(self, mock_embedding, mock_connection, mock_hana_db):
        """A tiny ## Prerequisites section must appear in exactly one output chunk."""
        # Build a doc where ## Prerequisites has ~10 tokens and the rest is bigger.
        prereq_text = "You need kubectl and helm installed."  # ~8 tokens
        big_section = _make_words(200, "description")

        doc_content = (
            f"# My Guide\n\n{big_section}\n\n## Prerequisites\n\n{prereq_text}\n\n## Installation\n\n{big_section}"
        )
        doc = Document(page_content=doc_content, metadata={"source": "guide.md"})

        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=20,
            max_chunk_token_count=1000,
        )
        chunks = list(indexer.get_document_chunks([doc]))

        # prereq_text must appear in at least one chunk
        prereq_in_chunks = [c for c in chunks if prereq_text in c.page_content]
        assert len(prereq_in_chunks) >= 1, "Prerequisites text must appear in at least one chunk"

        # prereq_text must appear in exactly one chunk (not duplicated)
        assert len(prereq_in_chunks) == 1, "Prerequisites text must not be duplicated across chunks"

    def test_single_tiny_chunk_kept(self, mock_embedding, mock_connection, mock_hana_db):
        """A document that is itself tiny (single chunk, too small) must be kept."""
        doc = Document(
            page_content="## Prerequisites\n\nInstall kubectl.",
            metadata={"source": "tiny.md"},
        )
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=20,
            max_chunk_token_count=1000,
        )
        chunks = list(indexer.get_document_chunks([doc]))
        # Must produce exactly one chunk and it must contain the content.
        assert len(chunks) == 1
        assert "Install kubectl" in chunks[0].page_content

    def test_tiny_first_chunk_merged_into_next(self, mock_embedding, mock_connection, mock_hana_db):
        """When the first chunk of a document is tiny it must be prepended to the second."""
        big_section = _make_words(200, "description")

        # Build a doc where H1 content is tiny (< 20 tokens) and H2 content is big.
        doc_content = (
            "# Title\n\n"
            "Tiny intro.\n\n"  # tiny H1 content
            f"## Section A\n\n{big_section}"
        )
        doc = Document(page_content=doc_content, metadata={"source": "first.md"})

        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=20,
            max_chunk_token_count=1000,
        )
        chunks = list(indexer.get_document_chunks([doc]))

        all_content = " ".join(c.page_content for c in chunks)
        assert "Tiny intro" in all_content, "Tiny intro text must not be dropped"

        # The tiny intro must have been merged into another chunk, not kept standalone.
        # Verify no chunk contains ONLY the tiny intro (i.e. it was merged, not isolated).
        standalone_tiny = [c for c in chunks if "Tiny intro" in c.page_content and "description" not in c.page_content]
        assert not standalone_tiny, "Tiny intro must be merged into the adjacent chunk, not kept as a standalone chunk"


class TestPreamblePreservation:
    """Content before the first header (preamble) must not be dropped."""

    def test_preamble_preserved_in_large_doc(self, mock_embedding, mock_connection, mock_hana_db):
        """Intro text before H2 sections must appear in a chunk titled with the H1."""
        # Build a doc: 200-token intro under H1, then three 600-token H2 sections.
        intro_words = _make_words(200, "intro")
        section_words = _make_words(300, "sectioncontent")

        doc_content = (
            "# Main Title\n\n"
            f"{intro_words}\n\n"
            f"## Section One\n\n{section_words}\n\n"
            f"## Section Two\n\n{section_words}\n\n"
            f"## Section Three\n\n{section_words}"
        )
        doc = Document(page_content=doc_content, metadata={"source": "large.md"})

        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=20,
            max_chunk_token_count=1000,
        )
        chunks = list(indexer.get_document_chunks([doc]))

        # Intro words must appear in at least one chunk.
        intro_chunks = [c for c in chunks if "intro" in c.page_content]
        assert intro_chunks, "Intro (preamble) text must appear in at least one chunk"

        # The chunk containing intro text must have 'Main Title' in its title metadata.
        intro_chunk = intro_chunks[0]
        assert "Main Title" in (intro_chunk.metadata.get("title") or ""), (
            f"Preamble chunk title should contain 'Main Title', got: {intro_chunk.metadata.get('title')}"
        )


class TestOversizedSectionSplitting:
    """Sections that exceed max_chunk_token_count at H3 level must be split."""

    def test_oversized_h3_section_split_into_parts(self, mock_embedding, mock_connection, mock_hana_db):
        """A 3000-token ### Reference section must produce multiple parts."""
        # Build a ~3000 token section.
        big_content = _make_words(3000, "word")

        doc_content = f"# API Reference\n\n## Module\n\n### Reference\n\n{big_content}"
        doc = Document(page_content=doc_content, metadata={"source": "ref.md"})

        max_tokens = 1000
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=20,
            max_chunk_token_count=max_tokens,
            chunk_overlap_tokens=100,
        )
        chunks = list(indexer.get_document_chunks([doc]))

        # Find the Reference chunks.
        ref_chunks = [c for c in chunks if "Reference" in (c.metadata.get("title") or "")]
        min_expected_parts = 3
        assert len(ref_chunks) >= min_expected_parts, f"Expected at least 3 Reference chunks, got {len(ref_chunks)}"

        # Each chunk must be within the size limit (+ overlap tolerance).
        for chunk in ref_chunks:
            chunk_tokens = _token_count(chunk.page_content)
            assert chunk_tokens <= max_tokens + 100, (
                f"Chunk '{chunk.metadata.get('title')}' has {chunk_tokens} tokens, exceeds limit {max_tokens + 100}"
            )

        # At least some chunks should have "(part X/Y)" in their title.
        part_chunks = [c for c in ref_chunks if "(part " in (c.metadata.get("title") or "")]
        assert part_chunks, "Oversized section chunks must have '(part X/Y)' in their title"

    def test_oversized_part_titles_numbered(self, mock_embedding, mock_connection, mock_hana_db):
        """Part titles must follow the '(part 1/N)' pattern."""
        big_content = _make_words(3000, "data")

        doc_content = f"# Docs\n\n## Chapter\n\n### Reference\n\n{big_content}"
        doc = Document(page_content=doc_content, metadata={"source": "docs.md"})

        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=20,
            max_chunk_token_count=1000,
            chunk_overlap_tokens=100,
        )
        chunks = list(indexer.get_document_chunks([doc]))

        part_titles = [c.metadata.get("title", "") for c in chunks if "(part " in (c.metadata.get("title") or "")]
        assert part_titles, "Expected at least one part-titled chunk"

        import re

        pattern = re.compile(r"\(part \d+/\d+\)")
        for title in part_titles:
            assert pattern.search(title), f"Title '{title}' does not match '(part X/Y)' pattern"


class TestCodeFencePreservation:
    """Fenced code blocks must never be split across chunk boundaries."""

    def test_no_code_fence_split(self, mock_embedding, mock_connection, mock_hana_db):
        """No fenced code block should appear in more than one chunk (split)."""
        fence = "```python\n" + "x = 1\n" * 50 + "```"

        doc_content = (
            f"# Guide\n\n## Usage\n\n### Example\n\nSome intro text.\n\n{fence}\n\nMore text after the code block."
        )
        doc = Document(page_content=doc_content, metadata={"source": "code.md"})

        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=20,
            max_chunk_token_count=200,
            chunk_overlap_tokens=10,
        )
        chunks = list(indexer.get_document_chunks([doc]))

        # Count chunks that contain an opening fence but no closing fence, or vice versa.
        for chunk in chunks:
            fence_opens = chunk.page_content.count("```python")
            fence_closes = chunk.page_content.count("```\n") + (1 if chunk.page_content.endswith("```") else 0)
            # A balanced chunk has equal opens and closes (simplified check).
            # Since the only code block is python, each chunk must have 0 or 1 complete block.
            assert fence_opens == 0 or fence_opens <= fence_closes, (
                f"Chunk appears to have an unclosed code fence: {chunk.page_content[:200]}"
            )

    def test_no_content_lost(self, mock_embedding, mock_connection, mock_hana_db):
        """Total characters across all chunks must be >= document characters minus header duplication."""
        # Use a corpus of docs with different content types.
        fence = "```yaml\nkey: value\nother: data\n```"
        docs = [
            Document(
                page_content=(
                    "# Title A\n\nIntro text.\n\n"
                    "## Section One\n\n" + _make_words(150, "alpha") + "\n\n"
                    f"### Detail\n\n{fence}\n\nMore info.\n\n"
                    "## Section Two\n\n" + _make_words(150, "beta")
                ),
                metadata={"source": "doc_a.md"},
            ),
            Document(
                page_content=(
                    "# Title B\n\n" + _make_words(300, "gamma") + "\n\n## Sub\n\n" + _make_words(50, "delta")
                ),
                metadata={"source": "doc_b.md"},
            ),
        ]

        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path="",
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=20,
            max_chunk_token_count=500,
            chunk_overlap_tokens=50,
        )

        for doc in docs:
            chunks = list(indexer.get_document_chunks([doc]))
            total_chunk_chars = sum(len(c.page_content) for c in chunks)
            # Allow a small reduction from header-line deduplication by the MarkdownHeaderTextSplitter
            # (it strips the leading header line from each sub-document), but no bulk content loss.
            # 95% is a tight floor -- the only expected reduction is from header lines.
            assert total_chunk_chars >= len(doc.page_content) * 0.95, (
                f"Too much content lost for {doc.metadata['source']}: "
                f"original {len(doc.page_content)} chars, "
                f"chunks total {total_chunk_chars} chars"
            )


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def manifest_artifact_dir(tmp_path):
    """A tiny synthetic pinakes artifact: two sources, one residue file, one excluded page.

    Mirrors tests/unit/utils/test_manifest.py's fixture, but the api-gateway page here has
    headers so it gets split into several chunks, letting the chunk-level metadata
    assertions below exercise the recursive path too.
    """
    root = tmp_path / "artifact"

    manifest = {
        "version": 1,
        "generated_at": "2026-09-16T00:00:00Z",
        "sources": {
            "istio": {
                "commit": "abc123",
                "pages": {
                    "docs/user/README.md": {
                        "title": "Istio Module",
                        "doc_type": "concept",
                        "section": "",
                        "sha256": "sha-readme",
                        "selected_by": "resolver",
                    },
                    "docs/user/second.md": {
                        "title": "Second Page",
                        "doc_type": "howto",
                        "section": "Guides",
                        "sha256": "sha-second",
                        "selected_by": "resolver",
                    },
                },
            },
            "api-gateway": {
                "commit": "def456",
                "pages": {
                    "docs/user/overview.md": {
                        "title": "API Gateway Overview",
                        "doc_type": "concept",
                        "section": "",
                        "sha256": "sha-overview",
                        "selected_by": "resolver",
                    }
                },
            },
        },
    }
    _write(root / "manifest.json", json.dumps(manifest))

    _write(
        root / "istio" / "meta.json",
        json.dumps(
            {
                "repo": "kyma-project/istio",
                "module": "istio",
                "base_url": "https://github.com/kyma-project/istio/blob/abc123",
                "commit": "abc123",
            }
        ),
    )
    _write(root / "istio" / "docs" / "user" / "README.md", "# Istio Module\nOverview content.")
    _write(root / "istio" / "docs" / "user" / "second.md", "# Second Page\nGuide content.")

    _write(
        root / "api-gateway" / "meta.json",
        json.dumps(
            {
                "repo": "kyma-project/api-gateway",
                "module": "api-gateway",
                "base_url": "https://github.com/kyma-project/api-gateway/blob/def456",
                "commit": "def456",
            }
        ),
    )
    _write(
        root / "api-gateway" / "docs" / "user" / "overview.md",
        "# API Gateway Overview\nIntro line.\n\n## Configuration\nConfig details go here.",
    )

    # Residue: left out by the resolver, never listed in the manifest -- must not be read.
    _write(root / "_residue" / "istio" / "docs" / "user" / "leftover.md", "# Leftover\nShould never be indexed.")

    # Exclude istio::docs/user/second.md via a still-valid decision (sha256 matches the manifest).
    decision = {
        "id": "istio::docs/user/second.md",
        "sha256": "sha-second",
        "decision": "exclude",
        "reason": "duplicate of another page",
        "by": "test",
        "at": "2026-09-16T00:00:00Z",
    }
    _write(root / "decisions.jsonl", json.dumps(decision) + "\n")

    return root


class TestManifestDrivenChunking:
    """Chunking a manifest-loaded corpus: only manifest pages are chunked, with curated metadata."""

    def test_only_manifest_pages_are_chunked(
        self, manifest_artifact_dir, mock_embedding, mock_connection, mock_hana_db
    ):
        docs = load_manifest_documents(str(manifest_artifact_dir))
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path=str(manifest_artifact_dir),
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=1,
            max_chunk_token_count=1000,
        )

        chunks = list(indexer.get_document_chunks(docs))

        page_ids = {chunk.metadata["page_id"] for chunk in chunks}
        assert page_ids == {"istio::docs/user/README.md", "api-gateway::docs/user/overview.md"}
        assert all("Leftover" not in chunk.page_content for chunk in chunks)
        assert all("Guide content." not in chunk.page_content for chunk in chunks)

    def test_chunks_carry_manifest_and_source_meta_metadata(
        self, manifest_artifact_dir, mock_embedding, mock_connection, mock_hana_db
    ):
        docs = load_manifest_documents(str(manifest_artifact_dir))
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path=str(manifest_artifact_dir),
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=1,
            max_chunk_token_count=1000,
        )

        chunks = list(indexer.get_document_chunks(docs))
        istio_chunks = [c for c in chunks if c.metadata["page_id"] == "istio::docs/user/README.md"]
        assert len(istio_chunks) == 1
        chunk = istio_chunks[0]

        assert chunk.metadata["module"] == "istio"
        assert chunk.metadata["repo"] == "kyma-project/istio"
        assert chunk.metadata["commit"] == "abc123"
        assert chunk.metadata["url"] == "https://github.com/kyma-project/istio/blob/abc123/docs/user/README.md"
        assert chunk.metadata["doc_type"] == "concept"
        assert chunk.metadata["section"] == ""
        assert chunk.metadata["path"] == "docs/user/README.md"
        assert chunk.metadata["sha256"] == "sha-readme"
        assert chunk.metadata["title"] == "Istio Module"

    def test_split_page_chunks_inherit_navigation_title_and_manifest_metadata(
        self, manifest_artifact_dir, mock_embedding, mock_connection, mock_hana_db
    ):
        """A page split by its H2 headers still carries the navigation title as a prefix,
        and every resulting chunk still carries the page's manifest/meta.json metadata."""
        docs = load_manifest_documents(str(manifest_artifact_dir))
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path=str(manifest_artifact_dir),
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="t",
            min_chunk_token_count=1,
            max_chunk_token_count=1,  # force splitting on every header
        )

        chunks = list(indexer.get_document_chunks(docs))
        gateway_chunks = [c for c in chunks if c.metadata["page_id"] == "api-gateway::docs/user/overview.md"]
        assert len(gateway_chunks) >= 1
        for chunk in gateway_chunks:
            assert chunk.metadata["title"].startswith("API Gateway Overview")
            assert chunk.metadata["module"] == "api-gateway"
            assert chunk.metadata["repo"] == "kyma-project/api-gateway"
            assert chunk.metadata["page_id"] == "api-gateway::docs/user/overview.md"
