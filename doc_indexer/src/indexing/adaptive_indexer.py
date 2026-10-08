import json
import os
import re
import time
from collections.abc import Generator, Iterable, Iterator

import tiktoken
from hdbcli import dbapi
from indexing.constants import HEADER1, HEADER2, HEADER3
from indexing.metadata import build_chunk_metadata
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_hana import HanaDB
from langchain_text_splitters import MarkdownHeaderTextSplitter
from utils.documents import load_documents
from utils.summary import build_report, emit_summary, github_step_summary_path, render_summary
from writers.base import RunDescriptor, Writer, new_run_id
from writers.hana import HanaWriter

from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE, DOCS_SUMMARY_PATH
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


def _writer_names(writer: Writer) -> list[str]:
    inner = getattr(writer, "writers", [writer])
    return [type(w).__name__.removesuffix("Writer").lower() for w in inner]


def _prepare_report(writer: Writer, run: RunDescriptor, module_counts: dict[str, int], seconds: float) -> dict:
    """Build the run report (incl. the previous run, queried before the flip) and hand it to the writer."""
    prev_fn = getattr(writer, "previous_stats", None)
    report: dict = build_report(run, _writer_names(writer), module_counts, seconds, prev_fn() if prev_fn else None)
    set_report = getattr(writer, "set_report", None)
    if set_report:
        set_report(report)
    return report


class AdaptiveSplitMarkdownIndexer:
    """
    Markdown indexer that adaptively splits documents based on token size thresholds,
    using hierarchical headers (H1->H2->H3) only when needed until H3 level is reached.
    """

    def __init__(
        self,
        docs_path: str,
        embedding: Embeddings,
        connection: dbapi.Connection | None = None,
        table_name: str | None = None,
        headers_to_split_on: list[tuple[str, str]] | None = None,
        min_chunk_token_count: int = 20,
        max_chunk_token_count: int = 1000,
        writer: Writer | None = None,
        embedding_model_name: str = "",
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
                self.manifest: dict[str, dict[str, str | None]] | None = json.load(fh)
            logger.info("Loaded fetch manifest", extra={"path": manifest_path})
        else:
            logger.warning(
                "No manifest.json found -- repo/commit metadata will be missing", extra={"path": manifest_path}
            )
            self.manifest = None

        self.embedding_model_name = embedding_model_name
        if writer is None:
            if connection is None:
                raise ValueError("Either a writer or a HANA connection is required.")
            writer = HanaWriter(HanaDB(connection=connection, embedding=embedding, table_name=table_name))
        self.writer = writer

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
        base_metadata: dict[str, str | list[str] | None] | None = None,
    ) -> Generator[Document]:
        tokens = len(encoding.encode(doc.page_content))

        if tokens <= self.min_chunk_token_count:
            return

        # If the document is smaller than the max chunk token count or the H3 level is reached, yield the document
        if tokens <= self.max_chunk_token_count or level >= len(HEADER_LEVELS):
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
            chunks = list(self._process_doc(doc, base_metadata=base_metadata))
            total = len(chunks)
            for idx, chunk in enumerate(chunks):
                heading: str = chunk.metadata.pop("_leaf_header", "") or ""
                yield Document(
                    page_content=chunk.page_content,
                    metadata={
                        **chunk.metadata,
                        "heading": heading,
                        "chunk_index": idx,
                        "total_chunks": total,
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
                yield Document(
                    page_content=(
                        f"# {chunk.metadata['title']}\n{chunk.page_content.split('\n', 1)[-1]}"
                        if chunk.page_content.strip().startswith(("#", "##", "###"))
                        else f"# {chunk.metadata['title']}\n\n{chunk.page_content}"
                    ),
                    metadata=chunk.metadata,
                )

    def _iter_batches(self, chunks: Iterable[Document]) -> Iterator[list[Document]]:
        batch: list[Document] = []
        for chunk in chunks:
            batch.append(chunk)
            if len(batch) >= CHUNKS_BATCH_SIZE:
                yield batch
                batch = []
        if batch:
            yield batch

    def index(self) -> None:
        """Chunks the markdown files and hands the chunks (and vectors, if needed) to the writer."""
        docs = load_documents(self.docs_path)
        all_chunks = self.process_document_titles(docs)

        writer = self.writer
        run = RunDescriptor(
            run_id=new_run_id(),
            embedding_model=self.embedding_model_name,
            dimensions=0,
            sources=self.manifest or {},
        )
        begun = False
        started = time.monotonic()
        module_counts: dict[str, int] = {}
        batch_count = 0
        total_chunk_number = 0
        try:
            for batch in self._iter_batches(all_chunks):
                vectors: list[list[float]] = []
                if writer.needs_embeddings:
                    vectors = self.embedding.embed_documents([c.page_content for c in batch])
                    if not begun:
                        run.dimensions = len(vectors[0])
                if not begun:
                    writer.begin(run)
                    begun = True
                writer.write(batch, vectors)
                batch_count += 1
                total_chunk_number += len(batch)
                for c in batch:
                    module = str(c.metadata.get("module") or "")
                    if module:
                        module_counts[module] = module_counts.get(module, 0) + 1
                logger.info(f"Indexed batch {batch_count} with {len(batch)} chunks")
                # Wait before processing next batch
                logger.debug("Rate limiting: sleeping 3s before next batch")
                time.sleep(3)

            if not begun:
                if writer.needs_embeddings:
                    raise ValueError("No chunks produced, refusing to write an empty index.")
                writer.begin(run)  # hana: keep existing behaviour (delete all)
            report = _prepare_report(writer, run, module_counts, time.monotonic() - started)
            writer.commit()
        except Exception:
            logger.exception(f"Error while indexing (batch {batch_count + 1})")
            writer.abort()
            raise

        logger.info(f"Successfully indexed {total_chunk_number} chunks (run {run.run_id}).")
        emit_summary(render_summary(report), DOCS_SUMMARY_PATH, github_step_summary_path())
