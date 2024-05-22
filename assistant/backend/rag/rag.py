from enum import Enum

from .retriever import WeaviateRetriever
from .query_translator import MultiQueryTranslator, HydeTranslator
from .rerank import LLMReRank

from helpers.models import (create_model, LLM_AZURE_EMBEDDINGS_ADA, LLM_AZURE_GPT35,
                            AICORE_LLM_DEPLOYMENT_ID_GEMINI_PRO, LLM_GEMINI_1_0_PRO, LLMModel)

# from flow_templates import RERANKER_PROMT_TEMPLATE


class QueryTranslationType(Enum):
    HYDE = "hypothetical document generation"
    MULTI_QUERY = "multi-query generation"


class RAG:
    reranker = LLMReRank(llm_model=LLMModel(deployment_id=AICORE_LLM_DEPLOYMENT_ID_GEMINI_PRO,
                                            model_name=LLM_GEMINI_1_0_PRO))

    def __init__(self, docs_path: str, weaviate_url: str,
                 query_translation_type: QueryTranslationType = QueryTranslationType.MULTI_QUERY):
        self.query_translator_type = query_translation_type
        self.retriever = WeaviateRetriever(docs_path, weaviate_url, create_model(LLM_AZURE_EMBEDDINGS_ADA))

        if query_translation_type == QueryTranslationType.HYDE:
            self.query_translator = HydeTranslator(create_model(LLM_AZURE_GPT35))
        elif query_translation_type == QueryTranslationType.MULTI_QUERY:
            self.query_translator = MultiQueryTranslator(create_model(LLM_AZURE_GPT35))
        else:
            raise ValueError(f"Query translation type {query_translation_type} is not supported")

    def retrieve(self, query: str, context: str):
        # Translate the question to a hypothetical document
        docs = []
        if self.query_translator_type == QueryTranslationType.MULTI_QUERY:
            queries = self.query_translator.transform(query, context)
            queries_list = queries.strip().split("\n")
            # add the original query to the list
            queries_list.append(query)

            all_docs = [self.retriever.retrieve(query, 3) for query in queries_list]
            docs = get_unique_contents(all_docs)
        else:
            hyde_query = self.query_translator.transform(query, context)
            docs = self.retriever.retrieve(hyde_query, 3)

        # re-rank the retrieved documents
        reranked_docs = ""
        if docs:
            reranked_docs = self.reranker.rerank(query, docs)
        reranked_docs = "\n\n--------------------------------\n\n".join(reranked_docs)
        return reranked_docs

    def get_retriever(self):
        return self.retriever.as_retriever()


def get_unique_contents(docs):
    unique_contents = set()
    unique_docs = []
    for sublist in docs:
        for doc in sublist:
            if doc.page_content not in unique_contents:
                unique_docs.append(doc)
                unique_contents.add(doc.page_content)
    unique_contents = list(unique_contents)
    return unique_contents
