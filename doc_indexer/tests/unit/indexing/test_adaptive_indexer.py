from unittest.mock import MagicMock, Mock, patch

import pytest
from indexing.adaptive_indexer import (
    AdaptiveSplitMarkdownIndexer,
    extract_first_title,
    remove_braces,
    remove_brackets,
    remove_header_brackets,
    remove_parentheses,
)
from langchain_core.documents import Document


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
    def test_process_document_titles(
        self, given_docs, wanted_results, mock_embedding, mock_connection, mock_hana_db
    ):
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
                assert processed_docs[i].page_content.startswith(
                    expected["content_startswith"]
                )

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
                            "## Subtitle 1\n"
                            "Subtitle content for testing ...\n"
                            "### Subsubtitle 1\n"
                            "Subsubtitle conten"
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
                        page_content=(
                            "## Subtitle 1\n" "Subtitle content for testing ..."
                        ),
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
                        page_content=(
                            "## Subtitle 1\n" "Subtitle content for testing ..."
                        ),
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
                            "Here is the the hello world Python code:\n"
                            "```python\n"
                            "print('Hello, World!') # prints 'Hello, World!' to the console\n"
                            "```\n"
                            "#### Subsubsubtitle 1\n"
                            "Subsubsubtitle 1 content for testing ..."
                        ),
                        metadata={
                            "source": "test4.md",
                            "title": "Title 1 - Subtitle 1 - Subsubtitle 1",
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
