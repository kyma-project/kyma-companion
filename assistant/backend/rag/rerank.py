from typing import Protocol
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from helpers.models import LLMModel
from clients.gemini_client import GeminiClient
from .prompt_templates import RERANKER_PROMT_TEMPLATE


class ReRank(Protocol):
    def rerank(self, query: str, documents: list[str], n_docs: int = 5) -> list[str]:
        ...


class LLMReRank:
    llm_model: LLMModel

    def __init__(self, llm_model: LLMModel):
        self.llm_model = llm_model

    def rerank(self, query: str, documents: list[str], n_docs: int = 5) -> list[str]:

        llm_client = None
        if self.llm_model.model_name.startswith("gemini"):
            llm_client = GeminiClient(deployment_id=self.llm_model.deployment_id,
                                      model_name=self.llm_model.model_name)

        retrieved_docs = ""
        for i, doc in enumerate(documents):
            escaped_doc = escape(doc)
            retrieved_docs += f"<document>\n{escaped_doc}</document>\n"
        rerank_prompt = f"{RERANKER_PROMT_TEMPLATE.format(query=query, retrieved_docs=retrieved_docs)}"

        reranked_docs = llm_client.invoke(
            [{"role": "user", "content": rerank_prompt}]
        )
        reranked_docs = reranked_docs.strip('`').lstrip('xml').strip()

        root = ET.fromstring(reranked_docs)
        # Extract the content of each <document> element into a list
        result = [document.text.strip() for document in root.findall('document')]
        return result
