from math import ceil
from typing import Any, Protocol

from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables.config import RunnableConfig

from agents.common.prompts import CHUNK_SUMMARIZER_PROMPT
from utils.chain import ainvoke_chain
from utils.logging import get_logger
from utils.models.factory import IModel
from utils.settings import TOTAL_CHUNKS_LIMIT

logger = get_logger(__name__)


class IToolResponseSummarizer(Protocol):
    """Protocol for IResponseConverter."""

    async def summarize_tool_response(
        self,
        tool_response: list[Any],
        user_query: str,
        config: RunnableConfig,
        nums_of_chunks: int,
    ) -> str:
        """summarize each chunk and return final summarized response."""
        ...


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
        nums_of_chunks: int = TOTAL_CHUNKS_LIMIT,
    ) -> str:
        """
        Summarize a list of tool responses by breaking them into chunks and summarizing each chunk.

        This method processes large tool responses by:
        1. Dividing the responses into manageable chunks
        2. Summarizing each chunk individually using a LLM
        3. Combining all chunk summaries into a final response

        Args:
            tool_response (List[Any]): The raw response data from a tool execution
            user_query (str): The original user query that prompted the tool execution
            config (RunnableConfig): Configuration for the chain execution
            nums_of_chunks (int): Number of chunks to divide the response into, default is max allowed chunks

        Returns:
            str: A consolidated summary of the tool response
        """
        # Divide the response list into chunks of equal size
        chunks = self._create_chunks_from_list(tool_response, nums_of_chunks)

        # Store summaries for each chunk
        chunk_summary = []

        # Process each chunk individually
        for i, chunk in enumerate(chunks):
            # Create a summarization chain
            chain = self._create_chain(user_query)

            # Process the chunk and generate a summary
            response = await ainvoke_chain(
                chain,
                {
                    "tool_response_chunk": chunk.page_content,
                },
                config=config,
            )

            logger.info(
                f"Tool Response chunk {i + 1}/{len(chunks)} summarized successfully"
            )
            chunk_summary.append(response)

        # Join all chunk summaries
        final_summary = "\n\n".join([item.content for item in chunk_summary])

        return final_summary
