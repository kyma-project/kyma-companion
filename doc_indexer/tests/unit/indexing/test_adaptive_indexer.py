from textwrap import dedent
from unittest.mock import MagicMock, Mock, patch

import pytest
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
        max_chunk_token_count=10,
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
            if "expected_chunks" in expected:
                assert indexer.chunk_size == expected["expected_chunks"]

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
        "docs",
        [
            (
                [
                    Document(
                        page_content=dedent(
                            """
                    # Title
                    Title content

                    ## Subtitle
                    Subtitle content

                    ### Subsubtitle
                    Subsubtitle content

                    #### Subsubsubtitle
                    Subsubsubtitle content
                    """
                        )
                    ),
                    Document(
                        page_content=dedent(
                            """
                    # Title
                    Title content

                    ## Subtitle
                    Subtitle content

                    ### Subsubtitle
                    Subsubtitle content

                    #### Subsubsubtitle
                    Subsubsubtitle content

                    # Title2
                    Title2 content

                    ## Subtitle2
                    Subtitle2 content

                    ### Subsubtitle2
                    Subsubtitle2 content

                    #### Subsubsubtitle2
                    Subsubsubtitle2 content
                    """
                        )
                    ),
                    Document(
                        page_content=dedent(
                            """
                    # Title
                    Title content
                    
                    ## Subtitle
                    Subtitle content
                    
                    ### Subsubtitle
                    Subsubtitle content
                    
                    #### Subsubsubtitle
                    Subsubsubtitle content
                    
                    # Title2
                    Title2 content
                    
                    ## Subtitle2
                    Subtitle2 content
                    
                    ### Subsubtitle2
                    Subsubtitle2 content
                    
                    #### Subsubsubtitle2
                    Subsubsubtitle2 content
                    
                    # Title3
                    Title3 content
                    
                    ## Subtitle3
                    Subtitle3 content
                    
                    ### Subsubtitle3
                    Subsubtitle3 content
                    
                    #### Subsubsubtitle3
                    Subsubsubtitle3 content
                    """
                        )
                    ),
                ]
            ),
        ],
    )
    def test_get_document_chunks(self, indexer, docs):
        chunks = indexer.get_document_chunks(docs)
        print("\n")
        for chunk in chunks:
            assert chunk is not None
            print(f"Title: {chunk.metadata.get("title")}")
            print(chunk.page_content)
            print("\n-------------------\n")
