from typing import List
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate

from agents.common.prompts import CHUNK_SUMMARIZER_PROMPT


class IterativeToolOutputSummarizer:
    """Chunk text, summarize each chunk iteratively, and concatenate results."""

    def __init__(self, llm, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.llm = llm
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )

    def summarize(self, text: str, user_query: str) -> str:
        """Split text into chunks, summarize each, and concatenate results."""
        docs = [Document(page_content=text)]
        chunks = self.text_splitter.split_documents(docs)

        full_summary = ""
        prompt_template = PromptTemplate(
            template=CHUNK_SUMMARIZER_PROMPT,
            input_variables=["text"],
            partial_variables={"query": user_query}  # Lock the query
        )

        for chunk in chunks:
            chunk_summary = self._summarize_chunk(chunk.page_content, prompt_template)
            full_summary += chunk_summary + "\n\n"  # Simply append!

        return full_summary.strip()

    def _summarize_chunk(self, chunk: str, prompt_template: PromptTemplate) -> str:
        """Summarize a single chunk with the query-focused prompt."""
        prompt = prompt_template.format(text=chunk)
        return self.llm(prompt).strip()
