import json

from langchain_core.documents import Document


def get_relevant_documents(docs_list: list[list[Document]], k: int = 60, limit: int = -1) -> list[Document]:
    """
    Get the most relevant documents from a list of documents.
    Note: This functions is inspired by the Reciprocal Rank Fusion (RRF) algorithm.
    Documents are ranked based on the number of times they appear in the list and their position in the list.
    Returns a list of unique documents sorted by their relevance score in descending order and capped by the limit.
    Assumption: The documents are unique within each list.
    :param docs_list: A list of lists of documents.
    :param k: The reciprocal rank factor.
    :param limit: The maximum number of documents to return. If -1, return all relevant unique documents.
    :return: A list of relevant documents.
    """
    if limit == 0:
        return []

    scores: dict[str, float] = {}
    docs_by_key: dict[str, Document] = {}

    for docs in docs_list:
        for rank, doc in enumerate(docs):
            doc_key = _get_document_key(doc)
            if doc_key not in scores:
                scores[doc_key] = 0.0
                docs_by_key[doc_key] = doc
            scores[doc_key] += 1 / (rank + k)

    relevant_docs = [docs_by_key[doc_key] for doc_key, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    return relevant_docs if limit < 0 else relevant_docs[:limit]


def _get_document_key(doc: Document) -> str:
    return json.dumps(
        {
            "page_content": doc.page_content,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
