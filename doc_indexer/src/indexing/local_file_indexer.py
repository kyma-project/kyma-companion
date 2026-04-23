import gc
import hashlib
import json
import tarfile
from datetime import UTC, datetime
from collections.abc import Generator
from pathlib import Path

from indexing.adaptive_indexer import (
    HEADER_LEVELS,
    encoding,
    extract_first_title,
    remove_header_brackets,
)
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from utils.documents import load_documents

from utils.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "kyma_docs"
# Small batches to limit ONNX Runtime peak memory on machines with ≤16 GB RAM
EMBED_BATCH_SIZE = 8
FASTEMBED_BATCH_SIZE = 4


def _clean_metadata(metadata: dict) -> dict:
    """Replace None values with empty strings so ChromaDB accepts the metadata."""
    return {k: (v if v is not None else "") for k, v in metadata.items()}


class LocalFileIndexer:
    """Indexes markdown documents into a local ChromaDB persistent store."""

    def __init__(
        self,
        docs_path: str,
        embedding: Embeddings,
        output_dir: str,
        embed_model_name: str = "",
        collection_name: str = COLLECTION_NAME,
        min_chunk_token_count: int = 20,
        max_chunk_token_count: int = 1000,
    ):
        self.docs_path = docs_path
        self.embedding = embedding
        self.output_dir = output_dir
        self.embed_model_name = embed_model_name
        self.collection_name = collection_name
        self.min_chunk_token_count = min_chunk_token_count
        self.max_chunk_token_count = max_chunk_token_count

    def _build_title(self, doc: Document) -> str:
        header1 = remove_header_brackets(doc.metadata.get("Header1", "")).strip()
        header2 = remove_header_brackets(doc.metadata.get("Header2", "")).strip()
        header3 = remove_header_brackets(doc.metadata.get("Header3", "")).strip()
        title_parts = [part for part in [header1, header2, header3] if part]
        return " - ".join(title_parts)

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
            yield from self._process_doc(chunk, level + 1, parent_title=title if level == 0 else parent_title)

    def _get_document_chunks(self, docs: list[Document]) -> Generator[Document]:
        for doc in docs:
            yield from self._process_doc(doc)

    def _process_document_titles(self, docs: list[Document]) -> Generator[Document]:
        for chunk in self._get_document_chunks(docs):
            if chunk.metadata.get("title") is None:
                yield chunk
            else:
                yield Document(
                    page_content=(
                        f"# {chunk.metadata['title']}\n{chunk.page_content.split(chr(10), 1)[-1]}"
                        if chunk.page_content.strip().startswith(("#", "##", "###"))
                        else f"# {chunk.metadata['title']}\n\n{chunk.page_content}"
                    ),
                    metadata=chunk.metadata,
                )

    def index(self) -> None:
        """Load, chunk, embed, and store documents in a ChromaDB persistent store."""
        # imported lazily so chromadb is only required when INDEX_TO_FILE=true
        import chromadb

        docs = load_documents(self.docs_path)
        chunks = list(self._process_document_titles(docs))
        logger.info(f"Prepared {len(chunks)} chunks for ChromaDB indexing.")

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=self.output_dir)

        try:
            client.delete_collection(self.collection_name)
            logger.info(f"Deleted existing ChromaDB collection '{self.collection_name}'.")
        except Exception:
            pass

        collection = client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        total = len(chunks)
        for i in range(0, total, EMBED_BATCH_SIZE):
            batch = chunks[i : i + EMBED_BATCH_SIZE]
            texts = [doc.page_content for doc in batch]
            metadatas = [_clean_metadata(doc.metadata) for doc in batch]
            ids = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
            vectors = self.embedding.embed_documents(texts, batch_size=FASTEMBED_BATCH_SIZE)
            collection.add(
                ids=ids,
                embeddings=vectors,
                documents=texts,
                metadatas=metadatas,
            )
            batch_num = i // EMBED_BATCH_SIZE + 1
            total_batches = (total - 1) // EMBED_BATCH_SIZE + 1
            logger.info(f"Indexed batch {batch_num} / {total_batches}")
            gc.collect()  # release ONNX Runtime intermediate tensors

        logger.info(f"Successfully indexed {total} chunks to ChromaDB at '{self.output_dir}'.")

        if self.embed_model_name:
            meta_path = Path(self.output_dir) / "meta.json"
            meta = {
                "embed_model": self.embed_model_name,
                "build_date": datetime.now(UTC).strftime("%Y-%m-%d"),
            }
            meta_path.write_text(json.dumps(meta))
            logger.info(f"Wrote meta.json: embed_model={self.embed_model_name}, build_date={meta['build_date']}")

    @staticmethod
    def package(output_dir: str, archive_path: str) -> None:
        """Package the ChromaDB directory into a .tar.gz archive."""
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(output_dir, arcname=Path(output_dir).name)
        logger.info(f"Created archive: {archive_path}")
