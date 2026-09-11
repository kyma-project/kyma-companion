import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import Generator

import tiktoken
from hdbcli import dbapi
from indexing.constants import HEADER1, HEADER2, HEADER3
from indexing.metadata import build_chunk_metadata
from indexing.preprocess import preprocess_markdown
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_hana import HanaDB
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from utils.documents import load_documents
from utils.hana import drop_table, rename_table

from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE, DATABASE_USER, INDEX_TO_FILE
from utils.utils import sanitize_table_name

encoding = tiktoken.encoding_for_model("gpt-4o")

logger = get_logger(__name__)

HEADER_LEVELS = [[HEADER1], [HEADER1, HEADER2], [HEADER1, HEADER2, HEADER3]]

_RETRY_WAIT_SECONDS = [2, 4, 8, 16, 32]
_MAX_RETRIES = len(_RETRY_WAIT_SECONDS)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception looks like a rate-limit error."""
    return "RateLimit" in type(exc).__name__ or "429" in str(exc)


def _add_documents_with_retry(db: HanaDB, batch: list[Document], batch_number: int) -> None:
    """Add a batch of documents to HanaDB, retrying on rate-limit errors.

    Args:
        db: The HanaDB instance to add documents to.
        batch: The list of documents to add.
        batch_number: The batch number (used for log messages only).
    """
    for attempt in range(_MAX_RETRIES + 1):
        try:
            db.add_documents(batch)
            return
        except Exception as exc:
            if not _is_rate_limit_error(exc):
                raise
            if attempt >= _MAX_RETRIES:
                raise
            wait = _RETRY_WAIT_SECONDS[attempt]
            logger.warning(
                f"Rate-limit error on batch {batch_number} (attempt {attempt + 1}/{_MAX_RETRIES}): retrying in {wait}s"
            )
            time.sleep(wait)


def deduplicate_documents(docs: list[Document]) -> list[Document]:
    """Remove duplicate documents by SHA-256 hash of their page content.

    When two documents collide on the same hash, the one whose source path
    contains 'docs/user/' is preferred.  If neither (or both) match, the first
    occurrence is kept.  Dropped paths are logged at INFO level.

    Args:
        docs: List of documents to deduplicate.

    Returns:
        A deduplicated list of documents in stable order.
    """
    seen: dict[str, Document] = {}
    result: list[Document] = []

    for doc in docs:
        digest = hashlib.sha256(doc.page_content.encode()).hexdigest()
        if digest not in seen:
            seen[digest] = doc
            result.append(doc)
        else:
            existing = seen[digest]
            existing_path = existing.metadata.get("source", "")
            new_path = doc.metadata.get("source", "")
            if "docs/user/" in new_path and "docs/user/" not in existing_path:
                # Prefer the docs/user/ path -- replace in-place
                idx = result.index(existing)
                result[idx] = doc
                seen[digest] = doc
                logger.info("Dropping duplicate document (keeping docs/user/ variant): %s", existing_path)
            else:
                logger.info("Dropping duplicate document: %s", new_path)

    return result


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


def split_preserving_code_fences(
    text: str,
    max_chunk_token_count: int,
    chunk_overlap_tokens: int,
    title: str,
) -> list[str]:
    """Split a text into chunks while preserving fenced code blocks as atomic units.

    Fenced code blocks (``` ... ```) are treated as indivisible -- if a block
    alone exceeds max_chunk_token_count, it is kept whole and a warning is
    emitted.  Non-code segments are split with RecursiveCharacterTextSplitter.

    Args:
        text: The markdown text to split.
        max_chunk_token_count: Maximum token count per chunk.
        chunk_overlap_tokens: Token overlap between consecutive chunks.
        title: Base title used to generate part titles.

    Returns:
        A list of text strings.  The caller is responsible for wrapping them in
        Document objects with the right metadata.
    """
    # Split the text into alternating non-code / fenced-code segments.
    # Pattern explanation:
    #   - Opening fence: ``` followed by optional info string and a newline.
    #   - Body: any content including lines that happen to start with ``` (e.g.
    #     documentation showing how to write a code fence).
    #   - Closing fence: a ``` that is at the beginning of a line (after \n)
    #     and is followed only by optional whitespace and a newline or end-of-string.
    #   Using a capturing group so re.split keeps the fence in the output list;
    #   odd-indexed segments are the fenced blocks, even-indexed are plain text.
    fence_pattern = re.compile(r"(```[^\n]*\n.*?\n```[ \t]*(?:\n|$))", re.DOTALL)
    segments = fence_pattern.split(text)  # odd indices are fenced blocks, even are plain text

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=max_chunk_token_count,
        chunk_overlap=min(chunk_overlap_tokens, max(0, max_chunk_token_count - 1)),
        separators=["\n#### ", "\n\n", "\n", " "],
    )

    parts: list[str] = []

    for i, segment in enumerate(segments):
        if not segment:
            continue
        if i % 2 == 1:
            # Fenced code block -- keep atomic.
            seg_tokens = len(encoding.encode(segment))
            if seg_tokens > max_chunk_token_count:
                logger.warning(
                    "Fenced code block in '%s' has %d tokens (limit %d); keeping whole.",
                    title,
                    seg_tokens,
                    max_chunk_token_count,
                )
            parts.append(segment)
        else:
            sub_parts = splitter.split_text(segment)
            parts.extend(sub_parts)

    if not parts:
        return []

    # Merge the parts back into chunks that respect max_chunk_token_count
    # (code blocks may bust the limit, but that is intentional per spec).
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for part in parts:
        part_tokens = len(encoding.encode(part))
        if current and current_tokens + part_tokens > max_chunk_token_count:
            chunks.append("\n".join(current))
            current = []
            current_tokens = 0
        current.append(part)
        current_tokens += part_tokens

    if current:
        chunks.append("\n".join(current))

    return chunks


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
        chunk_overlap_tokens: int = 100,
    ):
        """Initialize the AdaptiveSplitMarkdownIndexer.

        Args:
            docs_path: Path to the directory containing markdown files.
            embedding: Embedding model to use for indexing.
            connection: HANA database connection.
            table_name: Name of the HANA table to store the index.
            headers_to_split_on: List of header tuples to split on.
            min_chunk_token_count: Chunks with fewer tokens are merged into neighbours.
            max_chunk_token_count: Chunks larger than this are split further.
            chunk_overlap_tokens: Token overlap used when splitting oversized sections.
        """
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
        self.chunk_overlap_tokens = chunk_overlap_tokens

        # Load the fetch manifest if present; fall back gracefully when absent.
        manifest_path = os.path.join(docs_path, "manifest.json")
        if os.path.isfile(manifest_path):
            with open(manifest_path, encoding="utf-8") as fh:
                self.manifest: dict[str, dict[str, str | None]] | None = json.load(fh)
            logger.info("Loaded fetch manifest", extra={"path": manifest_path})
        else:
            logger.warning(
                "No manifest.json found -- repo/commit metadata will be missing", extra={"path": manifest_path}
            )
            self.manifest = None

        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=self.staging_table_name,
        )

        self.markdown_splitter_h1 = MarkdownHeaderTextSplitter(headers_to_split_on=[HEADER1])

        self.markdown_splitter_h2 = MarkdownHeaderTextSplitter(headers_to_split_on=[HEADER1, HEADER2])

        self.markdown_splitter_h3 = MarkdownHeaderTextSplitter(headers_to_split_on=[HEADER1, HEADER2, HEADER3])

    def _build_title(self, doc: Document) -> str:
        """Build a combined title from the headers H1, H2, H3 in the document metadata."""
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
        base_metadata: dict[str, str | None] | None = None,
    ) -> Generator[Document]:
        """Recursively split a document into chunks based on token count and header levels.

        Args:
            doc: The document to process.
            level: The current header level index into HEADER_LEVELS.
            parent_title: The title of the parent chunk.
            module: The module name for metadata.
            module_version: The module version for metadata.

        Yields:
            Documents representing individual chunks.
        """
        tokens = len(encoding.encode(doc.page_content))

        # If the document is smaller than the max chunk token count or the H3 level is
        # reached, yield the document (possibly after splitting oversized sections).
        if tokens <= self.max_chunk_token_count or level >= len(HEADER_LEVELS):
            if level >= len(HEADER_LEVELS) and tokens > self.max_chunk_token_count:
                # Oversized section at last header level -- split it.
                title = doc.metadata.get("title") or parent_title or extract_first_title(doc.page_content) or ""
                parts = split_preserving_code_fences(
                    doc.page_content,
                    self.max_chunk_token_count,
                    self.chunk_overlap_tokens,
                    title,
                )
                n = len(parts)
                for i, part in enumerate(parts, start=1):
                    part_title = f"{title} (part {i}/{n})" if n > 1 else title
                    part_meta = dict(base_metadata) if base_metadata else {}
                    part_meta["title"] = part_title
                    yield Document(
                        page_content=part,
                        metadata=part_meta,
                    )
            else:
                chunk_meta = dict(base_metadata) if base_metadata else {}
                chunk_meta["title"] = doc.metadata.get("title") or extract_first_title(doc.page_content)
                yield Document(
                    page_content=doc.page_content,
                    metadata=chunk_meta,
                )
            return

        # Split document using current header level
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADER_LEVELS[level], strip_headers=False)
        splitted_docs = markdown_splitter.split_text(doc.page_content)

        for sub_doc in splitted_docs:
            if not sub_doc.metadata:
                # Preamble before the first header -- keep it, don't skip.
                preamble_title = parent_title or doc.metadata.get("title") or extract_first_title(doc.page_content)
                preamble_meta = dict(base_metadata) if base_metadata else {}
                preamble_meta["title"] = preamble_title
                preamble_doc = Document(
                    page_content=sub_doc.page_content,
                    metadata=preamble_meta,
                )
                yield from self._process_doc(preamble_doc, level=len(HEADER_LEVELS), parent_title=parent_title)
                continue

            title = self._build_title(sub_doc)
            if not title:
                logger.warning("skip chunk - no title")
                continue

            if parent_title != title and (parent_title + " - ") not in title:
                title = parent_title + " - " + title if parent_title else title

            chunk_meta = dict(base_metadata) if base_metadata else {}
            chunk_meta["title"] = title
            chunk = Document(
                page_content=sub_doc.page_content,
                metadata=chunk_meta,
            )

            # Recursively process this chunk with next header level
            yield from self._process_doc(
                chunk, level + 1, parent_title=title if level == 0 else parent_title, base_metadata=base_metadata
            )

    def _merge_tiny_chunks(self, chunks: list[Document]) -> list[Document]:
        """Merge chunks with too few tokens into their neighbours within the same document.

        A chunk with tokens <= min_chunk_token_count is appended to the previous chunk
        of the same source document (or to the next one if it is the first chunk of that
        document).  A document that consists of a single tiny chunk is kept as is.

        Args:
            chunks: All chunks produced by _process_doc for a single source document.

        Returns:
            A new list where tiny chunks have been merged into adjacent chunks.
        """
        if not chunks:
            return chunks

        result: list[Document] = []

        for chunk in chunks:
            tokens = len(encoding.encode(chunk.page_content))
            if tokens <= self.min_chunk_token_count and result:
                # Append to previous chunk -- preserve its heading line.
                prev = result[-1]
                merged_content = prev.page_content + "\n\n" + chunk.page_content
                result[-1] = Document(
                    page_content=merged_content,
                    metadata=prev.metadata,
                )
            else:
                result.append(chunk)

        # Second pass: if the very first chunk is still tiny and there is a second chunk,
        # prepend it to the second chunk.
        min_two_chunks = 2
        if len(result) >= min_two_chunks:
            first_tokens = len(encoding.encode(result[0].page_content))
            if first_tokens <= self.min_chunk_token_count:
                merged_content = result[0].page_content + "\n\n" + result[1].page_content
                result[1] = Document(
                    page_content=merged_content,
                    metadata=result[1].metadata,
                )
                result.pop(0)

        return result

    def get_document_chunks(self, docs_to_chunk: list[Document]) -> Generator[Document]:
        """Recursively chunk documents based on the maximal token count with the headers H1, H2, H3.

        It splits the documents recursively if larger than given token number.
        It stops if the header level H3 is reached despite the token count.
        After splitting, tiny chunks are merged into their neighbours and statistics
        are logged at INFO level.

        Args:
            docs_to_chunk: List of documents to chunk.

        Yields:
            Chunked documents.
        """
        total_preamble_kept = 0
        total_tiny_merged = 0
        total_oversized_split = 0

        for doc in docs_to_chunk:
            source_path = doc.metadata.get("source", "")
            base_metadata = build_chunk_metadata(source_path, self.docs_path, self.manifest)
            raw_chunks = list(self._process_doc(doc, base_metadata=base_metadata))

            # Count preamble chunks (those whose title matches the parent doc title
            # and which came from a sub_doc with no metadata).
            # We use a simpler proxy: any chunk whose source title equals the document
            # title and whose page_content does NOT start with a markdown header is a
            # preamble candidate.  The exact count is not critical -- it is informational.
            doc_title = doc.metadata.get("title") or extract_first_title(doc.page_content)
            for chunk in raw_chunks:
                chunk_title = chunk.metadata.get("title")
                if chunk_title == doc_title and not chunk.page_content.lstrip().startswith("#"):
                    total_preamble_kept += 1

            # Count oversized-split chunks (titles containing " (part ").
            for chunk in raw_chunks:
                if " (part " in (chunk.metadata.get("title") or ""):
                    total_oversized_split += 1

            # Merge tiny chunks.
            merged_chunks = self._merge_tiny_chunks(raw_chunks)
            tiny_merged = len(raw_chunks) - len(merged_chunks)
            total_tiny_merged += tiny_merged

            yield from merged_chunks

        logger.info(
            "Chunking complete: preamble_kept=%d, tiny_merged=%d, oversized_split=%d",
            total_preamble_kept,
            total_tiny_merged,
            total_oversized_split,
        )

    def process_document_titles(self, docs: list[Document]) -> Generator[Document]:
        """Add a combined title to the document if the title is not already set.

        Clear the header from the document if it starts with the header.
        Yields documents one at a time instead of creating a full list.

        Args:
            docs: List of documents to process.

        Yields:
            Documents with updated titles.
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

    def build_chunks(self, docs: list[Document]) -> list[Document]:
        """Load, preprocess, chunk and title documents without touching HANA.

        This method is the pure chunking pipeline: it takes already-loaded documents,
        runs them through the adaptive splitter, and returns the final titled chunks.
        It is used by :meth:`index` internally and exposed for unit/snapshot testing
        without requiring a live HANA connection.

        Args:
            docs: Pre-loaded documents to chunk.

        Returns:
            List of titled, chunked :class:`~langchain_core.documents.Document` objects.
        """
        return list(self.process_document_titles(docs))

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
                    _add_documents_with_retry(self.db, batch, batch_count + 1)
                    batch_count += 1
                    total += len(batch)
                    logger.info(f"Indexed batch {batch_count} with {len(batch)} chunks into staging table")
                    batch = []

            if batch:
                _add_documents_with_retry(self.db, batch, batch_count + 1)
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
        # Preprocess each document before chunking
        preprocessed: list[Document] = []
        for doc in docs:
            page_url: str | None = doc.metadata.get("source")
            cleaned = preprocess_markdown(doc.page_content, page_url=page_url)
            preprocessed.append(Document(page_content=cleaned, metadata=doc.metadata))

        # Deduplicate by SHA-256 of cleaned text
        preprocessed = deduplicate_documents(preprocessed)

        all_chunks = self.process_document_titles(preprocessed)

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
