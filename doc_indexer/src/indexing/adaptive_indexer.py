import json
import re
import time
import uuid
from collections.abc import Generator

import tiktoken
from hdbcli import dbapi
from indexing.constants import HEADER1, HEADER2, HEADER3
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_hana import HanaDB
from langchain_text_splitters import MarkdownHeaderTextSplitter
from utils.documents import load_documents
from utils.hana import drop_table, rename_table

from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE, DATABASE_USER, INDEX_TO_FILE
from utils.utils import sanitize_table_name

encoding = tiktoken.encoding_for_model("gpt-4o")

logger = get_logger(__name__)

HEADER_LEVELS = [[HEADER1], [HEADER1, HEADER2], [HEADER1, HEADER2, HEADER3]]


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
        min_chunk_token_count: int = 20,
        max_chunk_token_count: int = 1000,
    ):
        self.headers_to_split_on = headers_to_split_on or [HEADER1, HEADER2, HEADER3]
        if not table_name:
            table_name = docs_path.split("/")[-1]
        table_name = sanitize_table_name(table_name)

        self.docs_path = docs_path
        self.table_name = table_name
        self.staging_table_name = sanitize_table_name(f"{table_name}_staging_{int(time.time())}")
        self.connection = connection
        self.embedding = embedding
        self.min_chunk_token_count = min_chunk_token_count
        self.max_chunk_token_count = max_chunk_token_count

        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=self.staging_table_name,
        )

        self.markdown_splitter_h1 = MarkdownHeaderTextSplitter(headers_to_split_on=[HEADER1])

        self.markdown_splitter_h2 = MarkdownHeaderTextSplitter(headers_to_split_on=[HEADER1, HEADER2])

        self.markdown_splitter_h3 = MarkdownHeaderTextSplitter(headers_to_split_on=[HEADER1, HEADER2, HEADER3])

    def _build_title(self, doc: Document) -> str:
        # the following lines build the combined title from the headers H1, H2, H3
        header1 = remove_header_brackets(doc.metadata.get("Header1", "")).strip()
        header2 = remove_header_brackets(doc.metadata.get("Header2", "")).strip()
        header3 = remove_header_brackets(doc.metadata.get("Header3", "")).strip()

        # Join non-empty headers with " - "
        title_parts = [part for part in [header1, header2, header3] if part]
        title = " - ".join(title_parts)

        return title

    def _process_doc(
        self,
        doc: Document,
        level: int = 0,
        parent_title: str = "",
        module: str | None = "kyma",
        module_version: str | None = "latest",
    ) -> Generator[Document]:
        tokens = len(encoding.encode(doc.page_content))

        if tokens <= self.min_chunk_token_count:
            return

        # If the document is smaller than the max chunk token count or the H3 level is reached, yield the document
        if tokens <= self.max_chunk_token_count or level >= len(HEADER_LEVELS):
            yield Document(
                page_content=doc.page_content,
                metadata={
                    "source": doc.metadata.get("source", ""),
                    "title": doc.metadata.get("title") or extract_first_title(doc.page_content),
                    "module": module,
                    "version": module_version,
                },
            )
            return
        # Split document using current header level
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADER_LEVELS[level], strip_headers=False)
        splitted_docs = markdown_splitter.split_text(doc.page_content)

        for sub_doc in splitted_docs:
            if not sub_doc.metadata:
                logger.warning("skip chunk - no metadata")
                continue

            title = self._build_title(sub_doc)
            if not title:
                logger.warning("skip chunk - no title")
                continue

            if parent_title != title and (parent_title + " - ") not in title:
                title = parent_title + " - " + title if parent_title else title

            chunk = Document(
                page_content=sub_doc.page_content,
                metadata={
                    "source": doc.metadata.get("source", ""),
                    "title": title,
                    "module": module,
                    "version": module_version,
                },
            )

            # Recursively process this chunk with next header level
            yield from self._process_doc(chunk, level + 1, parent_title=title if level == 0 else parent_title)

    def get_document_chunks(self, docs_to_chunk: list[Document]) -> Generator[Document]:
        """
        Recursively chunk documents based on the maximal token count with the headers H1, H2, H3.
        It splits the documents recursively if larger than given token number.
        It stops if the header level H3 is reached despite the token count.
        """

        for doc in docs_to_chunk:
            yield from self._process_doc(doc)

    def process_document_titles(self, docs: list[Document]) -> Generator[Document]:
        """
        Add a combined title to the document if the title is not already set.
        Clear the header from the document if it starts with the header.
        Yields documents one at a time instead of creating a full list.
        """
        for chunk in self.get_document_chunks(docs):
            if chunk.metadata.get("title") is None:
                yield chunk
            else:
                yield Document(
                    page_content=(
                        f"# {chunk.metadata['title']}\n{chunk.page_content.split('\n', 1)[-1]}"
                        if chunk.page_content.strip().startswith(("#", "##", "###"))
                        else f"# {chunk.metadata['title']}\n\n{chunk.page_content}"
                    ),
                    metadata=chunk.metadata,
                )

    def _insert_chunks_to_staging(self, all_chunks: Generator[Document]) -> int:
        """Insert all chunks into the staging table in batches.

        Returns the total number of chunks inserted.

        Raises RuntimeError if no chunks were produced (guards against overwriting
        the live table with an empty index) or if the DB row count does not match
        the number of chunks written (guards against partial writes).

        On any exception the staging table is dropped and the exception is re-raised.
        """
        batch: list[Document] = []
        batch_count = 0
        total = 0
        try:
            for chunk in all_chunks:
                batch.append(chunk)
                if len(batch) >= CHUNKS_BATCH_SIZE:
                    self.db.add_documents(batch)
                    batch_count += 1
                    total += len(batch)
                    logger.info(f"Indexed batch {batch_count} with {len(batch)} chunks into staging table")
                    batch = []
                    logger.debug("Rate limiting: sleeping 3s before next batch")
                    time.sleep(3)

            if batch:
                self.db.add_documents(batch)
                batch_count += 1
                total += len(batch)
                logger.info(f"Indexed final batch {batch_count} with {len(batch)} chunks into staging table")

            with self.connection.cursor() as cursor:
                cursor.execute(f'SELECT COUNT(*) FROM "{DATABASE_USER}"."{self.staging_table_name}"')
                row = cursor.fetchone()
            staged_count = row[0] if row else 0
            logger.info(f"Staging table '{self.staging_table_name}' has {staged_count} rows (expected {total}).")
            if total == 0:
                raise RuntimeError(
                    f"No chunks were produced for staging table '{self.staging_table_name}'. "
                    "Aborting swap to avoid overwriting the live table with an empty index."
                )
            if staged_count != total:
                raise RuntimeError(
                    f"Staging table row count mismatch: expected {total}, got {staged_count}. Aborting swap."
                )
        except Exception:
            logger.exception("Error during indexing into staging table. Dropping staging table.")
            drop_table(self.connection, DATABASE_USER, self.staging_table_name)
            raise

        return total

    def _swap_staging_to_live(self, old_table_name: str) -> None:
        """Atomic swap: rename live -> old, staging -> live, drop old.

        If the staging -> live rename fails, old is renamed back to live and the
        exception is re-raised.
        """
        rename_table(self.connection, DATABASE_USER, self.table_name, old_table_name, ignore_missing=True)
        try:
            rename_table(self.connection, DATABASE_USER, self.staging_table_name, self.table_name)
        except Exception:
            logger.exception(
                f"Failed to rename staging table '{self.staging_table_name}' to '{self.table_name}'. "
                f"Attempting to restore live table from '{old_table_name}'."
            )
            rename_table(self.connection, DATABASE_USER, old_table_name, self.table_name, ignore_missing=True)
            raise
        drop_table(self.connection, DATABASE_USER, old_table_name)

    def index(self) -> None:
        """Indexes the markdown files in the given directory.

        Uses a staging-table rename swap for atomicity:
        1. All chunks are inserted into a staging table.
        2. The row count is verified.
        3. The live table is renamed to a temporary name, the staging table is
           renamed to the live name, then the old live table is dropped.

        On any error before or during the swap the staging table is dropped and
        the live table is left untouched.
        """
        docs = load_documents(self.docs_path)
        all_chunks = self.process_document_titles(docs)

        if INDEX_TO_FILE:
            # write pretty to file
            timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
            uuid_str = str(uuid.uuid4())
            output_file_path = f"Kyma_Documentation_chunks_{timestamp}_{uuid_str}.json"
            with open(output_file_path, "w", encoding="utf-8") as out:
                # Convert Documents to dictionaries
                serializable_chunks = [
                    {"page_content": chunk.page_content, "metadata": chunk.metadata} for chunk in all_chunks
                ]
                json.dump({"kyma_docs": serializable_chunks}, fp=out, indent=2)
            logger.info(f"Indexed {len(serializable_chunks)} chunks.")
            logger.info(f"Chunks are stored in the file: {output_file_path}")
        else:
            old_table_name = f"{self.table_name}_old_{int(time.time())}"
            logger.info(
                f"Indexing into staging table '{self.staging_table_name}'; "
                f"live table is '{self.table_name}'; "
                f"old table will be '{old_table_name}'."
            )
            total = self._insert_chunks_to_staging(all_chunks)
            logger.info("Swapping staging table into live position...")
            self._swap_staging_to_live(old_table_name)
            logger.info(
                f"Successfully indexed {total} chunks into table '{self.table_name}' "
                f"(via staging table '{self.staging_table_name}')."
            )
