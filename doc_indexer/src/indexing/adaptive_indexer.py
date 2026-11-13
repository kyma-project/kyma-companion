import json
import os
import re
import time
import uuid
from collections.abc import Generator

import tiktoken
from hdbcli import dbapi
from indexing.constants import HEADER1, HEADER2, HEADER3
from indexing.html_table_splitter import HtmlTableParser
from indexing.metadata import build_chunk_metadata
from indexing.text_utils import extract_first_title, remove_header_brackets
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_hana import HanaDB
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from utils.documents import load_documents

from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE, INDEX_TO_FILE
from utils.utils import sanitize_table_name

# gpt-4o encoding is used as a stable proxy for token counting.
# The actual deployed model (gpt-4.1) uses a compatible tokenizer.
# Update this if switching to a model family with a different vocabulary.
_TOKENIZER_MODEL = "gpt-4o"
encoding = tiktoken.encoding_for_model(_TOKENIZER_MODEL)

_MARKDOWN_SEPARATORS = [r"\n#{1,6} ", "```\n", "\n\n", "\n", " ", ""]

_HTML_TABLE_LINE_RATIO_THRESHOLD = 0.2
# Fenced code blocks are stripped before counting HTML tag lines to avoid
# treating code examples (e.g. XML/HTML snippets in docs) as real HTML tables.
_FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)

HEADER_LEVELS = [[HEADER1], [HEADER1, HEADER2], [HEADER1, HEADER2, HEADER3]]


def _is_html_table_content(content: str, threshold: float) -> bool:
    """Return True if HTML table tags constitute more than *threshold* of lines.

    Fenced code blocks are excluded so that documentation examples containing
    HTML markup are not misclassified as HTML table content.
    """
    stripped = _FENCED_CODE_BLOCK_RE.sub("", content)
    lines = stripped.splitlines()
    total_lines = len(lines) or 1
    html_tag_lines = sum(
        1
        for line in lines
        if line.strip().startswith(("<table", "<tr", "<td", "<th", "</table", "</tr", "</td", "</th"))
    )
    return html_tag_lines / total_lines > threshold


logger = get_logger(__name__)


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
        self.embedding = embedding
        self.min_chunk_token_count = min_chunk_token_count
        self.max_chunk_token_count = max_chunk_token_count

        # Load the fetch manifest if present; fall back gracefully when absent.
        manifest_path = os.path.join(docs_path, "manifest.json")
        if os.path.isfile(manifest_path):
            with open(manifest_path, encoding="utf-8") as fh:
                self.manifest: dict[str, dict[str, str | list[str] | None]] | None = json.load(fh)
            logger.info("Loaded fetch manifest", extra={"path": manifest_path})
        else:
            logger.warning(
                "No manifest.json found -- repo/commit metadata will be missing", extra={"path": manifest_path}
            )
            self.manifest = None

        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

        self._markdown_splitter = RecursiveCharacterTextSplitter(
            separators=_MARKDOWN_SEPARATORS,
            chunk_size=max_chunk_token_count,
            chunk_overlap=0,
            length_function=lambda t: len(encoding.encode(t)),
            is_separator_regex=True,
        )

    def _build_title(self, doc: Document) -> str:
        header1 = remove_header_brackets(doc.metadata.get("Header1", "")).strip()
        header2 = remove_header_brackets(doc.metadata.get("Header2", "")).strip()
        header3 = remove_header_brackets(doc.metadata.get("Header3", "")).strip()

        # Join non-empty headers with " - "
        title_parts = [part for part in [header1, header2, header3] if part]
        title = " - ".join(title_parts)

        return title

    def _make_chunk_meta(
        self,
        doc: Document,
        base_metadata: dict[str, str | list[str] | None] | None,
    ) -> dict[str, str | list[str] | None]:
        """Build chunk metadata from base_metadata, inheriting title and leaf header from doc."""
        title = doc.metadata.get("title", "")
        leaf_header = doc.metadata.get("_leaf_header", "") or title
        meta = dict(base_metadata) if base_metadata else {}
        meta["title"] = title
        meta["_leaf_header"] = leaf_header
        return meta

    def _split_oversized(
        self,
        doc: Document,
        base_metadata: dict[str, str | list[str] | None] | None,
    ) -> Generator[Document]:
        """Route an oversized terminal chunk to the appropriate sub-splitter."""
        if _is_html_table_content(doc.page_content, _HTML_TABLE_LINE_RATIO_THRESHOLD):
            yield from self._split_html_table(doc, base_metadata)
        else:
            yield from self._split_markdown(doc, base_metadata)

    def _split_markdown(
        self,
        doc: Document,
        base_metadata: dict[str, str | list[str] | None] | None,
    ) -> Generator[Document]:
        """Split oversized plain-Markdown content using paragraph/heading boundaries."""
        chunk_meta = self._make_chunk_meta(doc, base_metadata)
        for text in self._markdown_splitter.split_text(doc.page_content):
            yield Document(page_content=text, metadata=dict(chunk_meta))

    def _split_html_table(
        self,
        doc: Document,
        base_metadata: dict[str, str | list[str] | None] | None,
    ) -> Generator[Document]:
        """Split a chunk whose content is dominated by an HTML table.

        Repeats intro_text, header_row, and outro_text in every emitted chunk.
        Falls through to _split_markdown if no <table> is found.
        """
        parser = HtmlTableParser()
        parser.feed(doc.page_content)
        parser.close()

        if not parser.tables:
            yield from self._split_markdown(doc, base_metadata)
            return

        chunk_meta = self._make_chunk_meta(doc, base_metadata)
        title = chunk_meta["title"]

        last_idx = len(parser.tables) - 1

        for table_idx, (intro, header_cells, data_rows) in enumerate(parser.tables):
            outro = parser.outro_text if table_idx == last_idx else ""
            header_row = " | ".join(header_cells) if header_cells else ""

            # Compute fixed overhead (intro + header row + outro) once per table so
            # the row budget stays constant regardless of how many rows we pack.
            fixed_parts = [p for p in [intro, header_row, outro] if p]
            fixed_text = "\n\n".join(fixed_parts)
            fixed_tokens = len(encoding.encode(fixed_text))
            row_budget = max(1, self.max_chunk_token_count - fixed_tokens)

            if not data_rows:
                # Table has a header but no data rows — emit the context as a single chunk
                # so intro, column headers, and outro are not silently dropped.
                yield self._assemble_table_chunk(intro, header_row, [], outro, chunk_meta, fixed_tokens)
                continue

            current_rows: list[str] = []
            current_tokens = 0

            for row_cells in data_rows:
                row_text = " | ".join(cell for cell in row_cells)
                row_tokens = len(encoding.encode(row_text))

                if current_rows and current_tokens + row_tokens > row_budget:
                    yield self._assemble_table_chunk(
                        intro,
                        header_row,
                        current_rows,
                        outro,
                        chunk_meta,
                        fixed_tokens + current_tokens,
                    )
                    current_rows = []
                    current_tokens = 0

                current_rows.append(row_text)
                current_tokens += row_tokens

                if row_tokens > row_budget:
                    logger.warning(
                        "html_table_splitter: single row exceeds token budget",
                        extra={
                            "title": title,
                            "path": (base_metadata or {}).get("path", ""),
                            "row_tokens": row_tokens,
                            "budget": row_budget,
                        },
                    )
                    yield self._assemble_table_chunk(
                        intro,
                        header_row,
                        current_rows,
                        outro,
                        chunk_meta,
                        fixed_tokens + current_tokens,
                    )
                    current_rows = []
                    current_tokens = 0

            if current_rows:
                yield self._assemble_table_chunk(
                    intro,
                    header_row,
                    current_rows,
                    outro,
                    chunk_meta,
                    fixed_tokens + current_tokens,
                )

    def _assemble_table_chunk(
        self,
        intro: str,
        header_row: str,
        row_texts: list[str],
        outro: str,
        chunk_meta: dict[str, str | list[str] | None],
        total_tokens: int,
    ) -> Document:
        """Assemble the page_content for one table chunk and log if oversized."""
        table_section = "\n".join(p for p in [header_row, "\n".join(row_texts)] if p)
        parts = [p for p in [intro, table_section, outro] if p]
        content = "\n\n".join(parts)
        if total_tokens > self.max_chunk_token_count:
            logger.warning(
                "html_table_splitter: chunk exceeds token limit",
                extra={
                    "title": chunk_meta.get("title", ""),
                    "tokens": total_tokens,
                    "limit": self.max_chunk_token_count,
                },
            )
        return Document(page_content=content, metadata=dict(chunk_meta))

    def _process_doc(
        self,
        doc: Document,
        level: int = 0,
        parent_title: str = "",
        base_metadata: dict[str, str | list[str] | None] | None = None,
    ) -> Generator[Document]:
        tokens = len(encoding.encode(doc.page_content))

        if tokens <= self.min_chunk_token_count:
            return

        if tokens <= self.max_chunk_token_count:
            chunk_meta = dict(base_metadata) if base_metadata else {}
            title = doc.metadata.get("title") or extract_first_title(doc.page_content)
            if not title:
                # Preamble chunk: content before the first heading has no title.
                # Fall back to the filename (without extension) so the chunk is still indexable.
                doc_path: str = (base_metadata or {}).get("path") or ""  # type: ignore[assignment]
                title = os.path.splitext(os.path.basename(doc_path))[0] or "unknown"
                logger.info("preamble chunk -- using filename as title", extra={"path": doc_path, "title": title})
            chunk_meta["title"] = title
            # Carry the raw leaf header set by the caller; fall back to the full title.
            chunk_meta["_leaf_header"] = doc.metadata.get("_leaf_header") or title
            yield Document(
                page_content=doc.page_content,
                metadata=chunk_meta,
            )
            return

        elif level >= len(HEADER_LEVELS):
            # All header levels exhausted — can't split further by heading.
            # Apply the same title fallback as the fits-in-budget branch so that
            # oversized preamble chunks don't reach _split_oversized with an empty title.
            if not doc.metadata.get("title"):
                preamble_path: str = (base_metadata or {}).get("path") or ""  # type: ignore[assignment]
                fallback_title = os.path.splitext(os.path.basename(preamble_path))[0] or "unknown"
                logger.info(
                    "preamble chunk -- using filename as title",
                    extra={"path": preamble_path, "title": fallback_title},
                )
                doc = Document(
                    page_content=doc.page_content,
                    metadata={**doc.metadata, "title": fallback_title, "_leaf_header": fallback_title},
                )
            # Route to the appropriate sub-splitter based on content type.
            yield from self._split_oversized(doc, base_metadata)
            return
        # Split document using current header level
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADER_LEVELS[level], strip_headers=False)
        splitted_docs = markdown_splitter.split_text(doc.page_content)

        for sub_doc in splitted_docs:
            if not sub_doc.metadata:
                # Preamble: content before the first heading has no header metadata.
                # Recurse so the terminal branch applies the filename-derived title fallback.
                yield from self._process_doc(sub_doc, level=len(HEADER_LEVELS), base_metadata=base_metadata)
                continue

            title = self._build_title(sub_doc)
            if not title:
                logger.warning("skip chunk - no title")
                continue

            # The deepest non-empty header on this sub_doc is the raw leaf heading.
            leaf_header = (
                remove_header_brackets(sub_doc.metadata.get("Header3", "")).strip()
                or remove_header_brackets(sub_doc.metadata.get("Header2", "")).strip()
                or remove_header_brackets(sub_doc.metadata.get("Header1", "")).strip()
            )

            if parent_title != title and (parent_title + " - ") not in title:
                # Prepend the H1 parent title so every chunk carries the full breadcrumb
                # (e.g. "Kyma Modules - Enable a Module"), but avoid doubling it when
                # the splitter has already embedded it (e.g. after a recursive call).
                title = parent_title + " - " + title if parent_title else title

            chunk_meta = dict(base_metadata) if base_metadata else {}
            chunk_meta["title"] = title
            chunk_meta["_leaf_header"] = leaf_header
            chunk = Document(
                page_content=sub_doc.page_content,
                metadata=chunk_meta,
            )

            # Recursively process this chunk with next header level
            yield from self._process_doc(
                chunk, level + 1, parent_title=title if level == 0 else parent_title, base_metadata=base_metadata
            )

    def get_document_chunks(self, docs_to_chunk: list[Document]) -> Generator[Document]:
        """
        Recursively chunk documents based on the maximal token count with the headers H1, H2, H3.
        It splits the documents recursively if larger than given token number.
        It stops if the header level H3 is reached despite the token count.
        """
        for doc in docs_to_chunk:
            source_path = doc.metadata.get("source", "")
            base_metadata = build_chunk_metadata(source_path, self.docs_path, self.manifest)
            for chunk in self._process_doc(doc, base_metadata=base_metadata):
                heading: str = chunk.metadata.pop("_leaf_header", "") or ""
                yield Document(
                    page_content=chunk.page_content,
                    metadata={
                        **chunk.metadata,
                        "heading": heading,
                    },
                )

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
                title = chunk.metadata["title"]
                heading = chunk.metadata.get("heading", "")
                first_line, _, rest = chunk.page_content.partition("\n")
                first_line_text = first_line.strip().lstrip("#").strip()
                if first_line_text in (title, heading):
                    # First line is the title or the leaf heading — replace it with
                    # the canonical combined title and drop the original heading line.
                    page_content = f"# {title}\n{rest}"
                else:
                    page_content = f"# {title}\n\n{chunk.page_content}"
                yield Document(page_content=page_content, metadata=chunk.metadata)

    def index(self) -> None:
        """Indexes the markdown files in the given directory."""

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
            total_chunk_number = 0
            try:
                for chunk in all_chunks:
                    batch.append(chunk)
                    if len(batch) >= CHUNKS_BATCH_SIZE:
                        # Process the current batch
                        self.db.add_documents(batch)
                        batch_count += 1
                        total_chunk_number += len(batch)
                        logger.info(f"Indexed batch {batch_count} with {len(batch)} chunks")

                        # Clear the batch
                        batch = []

                        # Wait before processing next batch
                        logger.debug("Rate limiting: sleeping 3s before next batch")
                        time.sleep(3)

                # Process any remaining documents in the final batch
                if batch:
                    self.db.add_documents(batch)
                    batch_count += 1
                    total_chunk_number += len(batch)
                    logger.info(f"Indexed final batch {batch_count} with {len(batch)} chunks")

            except Exception:
                logger.exception(f"Error while storing documents batch {batch_count + 1} in HanaDB")
                raise

            logger.info(f"Successfully indexed {total_chunk_number} markdown files chunks in table {self.table_name}.")
