from langchain_core.documents import Document

from rag.reranker.utils import str_to_document, document_to_str


def get_relevant_documents(docs_list: list[list[Document]], k: int = 60, limit: int = 10) -> list[Document]:
    """
    Get the most relevant documents from a list of documents.
    Note: This functions is inspired by the Reciprocal Rank Fusion (RRF) algorithm.
    Documents are ranked based on the number of times they appear in the list and their position in the list.
    Returns a list of unique documents sorted by their relevance score in descending order and capped by the limit.
    Assumption: The documents are unique within each list.
    :param docs_list: A list of lists of documents.
    :param k: The reciprocal rank factor.
    :param limit: The maximum number of documents to return.
    :return: A list of relevant documents.
    """
    scores = {}
    for docs in docs_list:
        for rank, doc in enumerate(docs):
            doc_str = document_to_str(doc)
            if doc_str not in scores:
                scores[doc_str] = 0
            scores[doc_str] += 1 / (rank + k)
    relevant_docs = [
        str_to_document(doc_str) for doc_str, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ]
    return relevant_docs[:limit]
