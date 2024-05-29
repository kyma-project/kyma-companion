from typing import Protocol, List
import re

from langchain_community.document_loaders.text import TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_community.document_loaders import DirectoryLoader
import weaviate
from weaviate.connect import ConnectionParams
from weaviate.classes.init import AdditionalConfig, Timeout
from langchain_weaviate.vectorstores import WeaviateVectorStore


class Retriever(Protocol):
    def index(self, docs_path: str) -> None:
        ...

    def retrieve(self, query: str, top_k: int) -> list:
        ...

    def as_retriever(self):
        ...


class WeaviateRetriever:
    db = None
    client = None

    def __init__(self, docs_path: str, url: str, embeddings, force_index=False):
        self.client = create_weaviate_client(url)
        self.client.connect()

        # extract the last word from the docs_path: ../flow/kyma_docs -> kyma_docs
        index_name = docs_path.split("/")[-1]

        self.index_name = index_name
        self.embeddings = embeddings
        # Connect to the Weaviate DB if the index exists
        if self.client.collections.exists(index_name) and not force_index:
            self.db = WeaviateVectorStore(self.client, index_name, "text", embeddings)
        else:
            # create index from the docs
            self.index(docs_path)

    def index(self, docs_path):
        # load the documents
        loader = DirectoryLoader(docs_path, loader_cls=TextLoader, recursive=True)
        documents = loader.load()
        # markdown_files = load_markdown_files(docs_path)

        # split the documents into chunks
        headers_to_split_on = [("#", "Header1")]
        text_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
        all_chunks: List[Document] = []
        for doc in documents:
            # if the chunk doesn't contain <!-- .... -->
            chunks = text_splitter.split_text(doc.page_content)
            all_chunks.extend(
                [chunk for chunk in chunks if chunk.page_content.strip()]
            )

        # create the index and store it
        print(f"Indexing {len(all_chunks)} markdown files chunks for {self.index_name}...")
        self.db = WeaviateVectorStore.from_documents(
            all_chunks, self.embeddings, client=self.client, index_name=self.index_name
        )

    def as_retriever(self):
        return self.db.as_retriever()

    def retrieve(self, query: str, top_k: int = 4, min_similarity: float = 0.7) -> list:
        docs = self.db.similarity_search_with_relevance_scores(query, top_k, score_threshold=min_similarity)
        result = [doc[0] for doc in docs]
        return result


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def create_weaviate_client(url: str):
    client = weaviate.WeaviateClient(
        connection_params=ConnectionParams.from_url(
            url=url,
            grpc_port=50051,
            grpc_secure=False,
        ),
        additional_config=AdditionalConfig(
            timeout=Timeout(init=2, query=45, insert=120),  # Values in seconds
        ),
    )
    return client
