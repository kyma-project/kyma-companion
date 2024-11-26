from langchain_core.documents import Document

from rag.reranker.utils import str_to_document, document_to_str

# TODO(marcobebway) change input from list[Document] to list[list[Document]]
# this is to respect the rank of each document when answering other queries.
def get_relevant_documents(docs: list[Document], k=60, limit=10) -> list[Document]:
    """TODO(marcobebway)"""
    scores = {}
    for rank, doc in enumerate(docs):
        doc_str = document_to_str(doc)
        if doc_str not in scores:
            scores[doc_str] = 0
        scores[doc_str] += 1 / (rank + k)
    relevant_docs = [
        str_to_document(doc_str) for doc_str, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ]
    return relevant_docs[:limit]
