from typing import List, Any
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings
from langchain.prompts import PromptTemplate
from langchain_core.runnables.config import RunnableConfig
from agents.common.prompts import CHUNK_SUMMARIZER_PROMPT
from utils.chain import ainvoke_chain
from utils.models.factory import IModel


class ToolResponseSummarizer:
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

    def _create_chunks(
        self, tool_response: str, nums_of_chunks: int
    ) -> list[Document] | None:
        """Split text into chunks"""
        chunk_size = self._dynamic_chunk_size_from_text(tool_response, nums_of_chunks)
        chunk_overlap = 100
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " "],
        )
        docs = [Document(page_content=tool_response)]

        return text_splitter.split_documents(docs)

    async def summarize_tool_response(
        self,
        tool_response: str,
        user_query: str,
        config: RunnableConfig,
        nums_of_chunks: int,
    ) -> str:
        """summarize each chunk and return final summarized response."""

        chunks = self._create_chunks(tool_response, nums_of_chunks)

        chunk_summary = []

        for chunk in chunks:
            chain = self._create_chain(user_query)
            # invoke the chain.
            response = await ainvoke_chain(
                chain,
                {
                    "tool_response_chunk": chunk.page_content,
                },
                config=config,
            )
            chunk_summary.append(response)

        return "\n\n".join([item.content for item in chunk_summary])
