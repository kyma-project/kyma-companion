import json
import re
import time
import uuid
from collections.abc import Generator

from hdbcli import dbapi
from indexing.contants import HEADER1, HEADER2, HEADER3
from langchain.schema import Document
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain_community.vectorstores import HanaDB
from langchain_core.embeddings import Embeddings

from utils.documents import load_documents
from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE

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


class AdvancedMarkdownIndexer:
    """Markdown indexer implements indexing markdown files into HanaDB."""

    def __init__(
        self,
        docs_path: str,
        embedding: Embeddings,
        connection: dbapi.Connection,
        table_name: str | None = None,
        headers_to_split_on: list[tuple[str, str]] | None = None,
    ):
        self.headers_to_split_on = headers_to_split_on or [HEADER1, HEADER2, HEADER3]
        if not table_name:
            table_name = docs_path.split("/")[-1]

        self.docs_path = docs_path
        self.table_name = table_name
        self.embedding = embedding

        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.headers_to_split_on
        )

    def get_document_chunks(
        self, full_doc: Document
    ) -> Generator[Document, None, None]:
        """
        Open a given file and chunk it.

        Skip all chunks, which:
        - Don't have a header/title
        - Don't have metadata

        yields the chunks from such a file.
        """
        splitted_docs = self.markdown_splitter.split_text(full_doc.page_content)
        for s_doc in splitted_docs:
            ## skip, if there is no metadata
            if not s_doc.metadata:
                print("  skip chunk - no metadata")
                continue
            header1 = remove_header_brackets(s_doc.metadata.get("Header1", "")).strip()
            header2 = remove_header_brackets(s_doc.metadata.get("Header2", "")).strip()
            header3 = remove_header_brackets(s_doc.metadata.get("Header3", "")).strip()
            title = (
                (" - ".join([header1, header2, header3]))
                .strip()
                .strip("-")
                .strip()
                .strip("-")
            )
            if not title:
                print("skip chunk - no title")
                continue

            yield Document(
                page_content="#" + title + "\n\n" + s_doc.page_content,
                metadata={
                    "source": full_doc.metadata.get("source", ""),
                    "title": title,
                    "module": "Kyma Module",
                    "version": "1.2.1",
                },
            )

    def index(self) -> None:
        """Indexes the markdown files in the given directory."""

        docs = load_documents(self.docs_path)

        # chunk the documents by the headers
        all_chunks = [chunk for doc in docs for chunk in self.get_document_chunks(doc)]

        logger.info(
            f"Indexing {len(all_chunks)} markdown files chunks for {self.table_name}..."
        )

        # counter = 0
        # for i, d in enumerate(all_chunks):
        #     if len(d.page_content) < 80:
        #         counter += 1
        #         print(
        #             "{:04} - {}\n{}\n------".format(
        #                 i, d.metadata["title"], d.page_content
        #             )
        #         )
        # print(counter, "Entries")

        ## write pretty to file
        timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
        uuid_str = str(uuid.uuid4())
        OUTPUT_FILE_PATH = f"Kyma_Documentation_chunks_{timestamp}_{uuid_str}.json"
        with open(OUTPUT_FILE_PATH, "w", encoding="utf-8") as out:
            # Convert Documents to dictionaries
            serializable_chunks = [
                {"page_content": chunk.page_content, "metadata": chunk.metadata}
                for chunk in all_chunks
            ]
            json.dump({"kyma_docs": serializable_chunks}, fp=out, indent=2)

        logger.info("Deleting existing index in HanaDB...")
        try:
            self.db.delete(filter={})
        except Exception:
            logger.exception("Error while deleting existing documents in HanaDB.")
            raise
        logger.info("Successfully deleted existing documents in HanaDB.")

        logger.info("Indexing and storing indexes to HanaDB...")
        for i in range(0, len(all_chunks), CHUNKS_BATCH_SIZE):
            batch = all_chunks[i : i + CHUNKS_BATCH_SIZE]
            try:
                # Add current batch of documents
                self.db.add_documents(batch)
                logger.info(
                    f"Indexed batch {i//CHUNKS_BATCH_SIZE + 1} of {len(all_chunks)//CHUNKS_BATCH_SIZE + 1}"
                )

                # Wait 3 seconds before processing next batch
                if i + CHUNKS_BATCH_SIZE < len(all_chunks):
                    time.sleep(3)

            except Exception as e:
                logger.error(
                    f"Error while storing documents batch {i//CHUNKS_BATCH_SIZE + 1} in HanaDB: {str(e)}"
                )
                raise

        logger.info(f"Successfully indexed {len(all_chunks)} markdown files chunks.")
