from math import ceil
from typing import Any

from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables.config import RunnableConfig

from agents.common.prompts import CHUNK_SUMMARIZER_PROMPT
from utils.chain import ainvoke_chain
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


class ToolResponseSummarizer:
    """Summarize the tool response by chunking"""

    def __init__(self, model: IModel | Embeddings):
        self.model = model

    def _create_chain(self, user_query: str) -> Any:
        """Summarize a single chunk with the query-focused prompt."""
        agent_prompt = PromptTemplate(
            template=CHUNK_SUMMARIZER_PROMPT,
            input_variables=["tool_response_chunk"],
            partial_variables={"query": user_query},
        )

        return agent_prompt | self.model.llm

    def _dynamic_chunk_size_from_text(
        self, tool_response: str, target_num_chunks: int = 10
    ) -> int:
        """calculate chunk size based on tool response"""
        total_chars = len(tool_response)
        return max(1, total_chars // target_num_chunks)

    def _create_chunks_from_list(
        self, tool_response: list[Any], nums_of_chunks: int
    ) -> list[Document]:
        """Split a list of K8s items into a specific number of Document chunks"""

        chunk_size = ceil(len(tool_response) / nums_of_chunks)
        chunks = []

        if tool_response:
            for i in range(0, len(tool_response), chunk_size):
                chunk_items = tool_response[i : i + chunk_size]
                text = "\n\n".join([str(item) for item in chunk_items])
                chunks.append(Document(page_content=text))

        return chunks


    async def summarize_tool_response(
        self,
        tool_response: list[Any],
        user_query: str,
        config: RunnableConfig,
        nums_of_chunks: int,
    ) -> str:
        """summarize each chunk and return final summarized response."""

        chunks = self._create_chunks_from_list(tool_response, nums_of_chunks)

        chunk_summary = []

        for i, chunk in enumerate(chunks):
            chain = self._create_chain(user_query)
            # invoke the chain.
            response = await ainvoke_chain(
                chain,
                {
                    "tool_response_chunk": chunk.page_content,
                },
                config=config,
            )
            logger.info(f"Tool Response chunk - {i+1} summarized successfully")
            chunk_summary.append(response)

        return "\n\n".join([item.content for item in chunk_summary])
