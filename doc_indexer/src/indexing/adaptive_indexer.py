import re
import time
from collections.abc import Generator

import tiktoken
from hdbcli import dbapi
from indexing.contants import HEADER1, HEADER2, HEADER3
from langchain_community.vectorstores import HanaDB
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter

from utils.documents import load_documents
from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE

encoding = tiktoken.encoding_for_model("gpt-4o")

logger = get_logger(__name__)


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
        ## check of something was removed
        if len(temp_text) < current_length:
            current_length = len(temp_text)
        else:
            break
    return temp_text


class AdaptiveSplitMarkdownIndexer:
    """
    Markdown indexer that adaptively splits documents based on token size thresholds,
    using hierarchical headers (H1->H2->H3) only when needed until H3 level is reached.
    """

    def __init__(
        self,
        docs_path: str,
        embedding: Embeddings,
        connection: dbapi.Connection,
        table_name: str | None = None,
        headers_to_split_on: list[tuple[str, str]] | None = None,
        smallest_chunk_length: int = 20,
        largest_chunk_length: int = 1000,
    ):
        self.headers_to_split_on = headers_to_split_on or [HEADER1, HEADER2, HEADER3]
        if not table_name:
            table_name = docs_path.split("/")[-1]

        self.docs_path = docs_path
        self.table_name = table_name
        self.embedding = embedding
        self.smallest_chunk_length = smallest_chunk_length
        self.largest_chunk_length = largest_chunk_length
        self.chunk_size = 0

        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

        self.markdown_splitter_h1 = MarkdownHeaderTextSplitter(
            headers_to_split_on=[HEADER1]
        )

        self.markdown_splitter_h2 = MarkdownHeaderTextSplitter(
            headers_to_split_on=[HEADER1, HEADER2]
        )

        self.markdown_splitter_h3 = MarkdownHeaderTextSplitter(
            headers_to_split_on=[HEADER1, HEADER2, HEADER3]
        )

    def _build_title(self, s_doc: Document) -> str:
        # the following lines build the combined title from the headers H1, H2, H3
        header1 = remove_header_brackets(s_doc.metadata.get("Header1", "")).strip()
        header2 = remove_header_brackets(s_doc.metadata.get("Header2", "")).strip()
        header3 = remove_header_brackets(s_doc.metadata.get("Header3", "")).strip()
        return (
            (" - ".join([header1, header2, header3]))
            .strip()
            .strip("-")
            .strip()
            .strip("-")
            .strip()
        )

    def get_document_chunks(
        self, docs_to_chunk: list[Document]
    ) -> Generator[Document, None, None]:
        """Recursively chunk documents based on token length and headers."""
        header_levels = [[HEADER1], [HEADER1, HEADER2], [HEADER1, HEADER2, HEADER3]]

        def process_doc(
            doc: Document, level: int = 0, parent_title: str = ""
        ) -> Generator[Document, None, None]:
            tokens = len(encoding.encode(doc.page_content))

            if tokens <= self.smallest_chunk_length:
                return

            # If the document is smaller than the largest chunk length or the H3 level is reached, yield the document
            if tokens <= self.largest_chunk_length or level >= len(header_levels):
                yield doc
                return
            # Split document using current header level
            markdown_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=header_levels[level], strip_headers=False
            )
            splitted_docs = markdown_splitter.split_text(doc.page_content)

            for s_doc in splitted_docs:
                if not s_doc.metadata:
                    print("  skip chunk - no metadata")
                    continue

                title = self._build_title(s_doc)
                if not title:
                    print("skip chunk - no title")
                    continue

                if parent_title != title and (parent_title + " - ") not in title:
                    title = parent_title + " - " + title if parent_title else title

                chunk = Document(
                    page_content=s_doc.page_content,
                    metadata={
                        "source": doc.metadata.get("source", ""),
                        "title": title,
                        "module": "Kyma Module",
                        "version": "1.2.1",
                    },
                )

                # Recursively process this chunk with next header level
                yield from process_doc(
                    chunk, level + 1, parent_title=title if level == 0 else parent_title
                )

        for doc in docs_to_chunk:
            yield from process_doc(doc)

    def process_document_titles(
        self, docs: list[Document]
    ) -> Generator[Document, None, None]:
        """
        Add a combined title to the document if the title is not already set.
        Clear the header from the document if it starts with the header.
        Yields documents one at a time instead of creating a full list.
        """
        for counter, chunk in enumerate(self.get_document_chunks(docs)):
            if chunk.metadata.get("title") is None:
                yield chunk
            else:
                yield Document(
                    page_content=(
                        f"# {chunk.metadata['title']}\n\n{chunk.page_content.split('\n', 1)[-1]}"
                        if chunk.page_content.strip().startswith(("#", "##", "###"))
                        else f"# {chunk.metadata['title']}\n\n{chunk.page_content}"
                    ),
                    metadata=chunk.metadata,
                )
        self.chunk_size = counter
        logger.info(
            f"Indexing {counter} markdown files chunks for {self.table_name}..."
        )

    def index(self) -> None:
        """Indexes the markdown files in the given directory."""

        docs = load_documents(self.docs_path)
        all_chunks = self.process_document_titles(docs)

        logger.info("Deleting existing index in HanaDB...")
        try:
            self.db.delete(filter={})
        except Exception:
            logger.exception("Error while deleting existing documents in HanaDB.")
            raise
        logger.info("Successfully deleted existing documents in HanaDB.")

        logger.info("Indexing and storing indexes to HanaDB...")
        batch = []
        batch_count = 0

        try:
            for chunk in all_chunks:
                batch.append(chunk)
                if len(batch) >= CHUNKS_BATCH_SIZE:
                    # Process the current batch
                    self.db.add_documents(batch)
                    batch_count += 1
                    logger.info(f"Indexed batch {batch_count} with {len(batch)} chunks")

                    # Clear the batch
                    batch = []

                    # Wait before processing next batch
                    time.sleep(3)

            # Process any remaining documents in the final batch
            if batch:
                self.db.add_documents(batch)
                batch_count += 1
                logger.info(
                    f"Indexed final batch {batch_count} with {len(batch)} chunks"
                )

        except Exception as e:
            logger.error(
                f"Error while storing documents batch {batch_count + 1} in HanaDB: {str(e)}"
            )
            raise

        logger.info(f"Successfully indexed {self.chunk_size} markdown files chunks.")
