from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain.schema import Document

from agents.common.chunk_summarizer import ToolResponseSummarizer
from agents.common.prompts import CHUNK_SUMMARIZER_PROMPT


class TestToolResponseSummarizer:
    @pytest.fixture
    def model_mock(self):
        model = Mock()
        model.llm = Mock()
        return model

    @pytest.fixture
    def summarizer(self, model_mock):
        return ToolResponseSummarizer(model_mock)

    def test_init(self, model_mock):
        # when
        summarizer = ToolResponseSummarizer(model_mock)

        # then
        assert summarizer.model == model_mock

    @patch("agents.common.chunk_summarizer.PromptTemplate")
    def test_create_chain(self, mock_prompt_template, summarizer):
        # given
        user_query = "sample query"
        mock_chain = Mock()
        mock_prompt_template.return_value.__or__.return_value = mock_chain

        # when
        summarizer._create_chain(user_query)

        mock_prompt_template.assert_called_once_with(
            template=CHUNK_SUMMARIZER_PROMPT,
            input_variables=["tool_response_chunk"],
            partial_variables={"query": user_query},
        )

    @pytest.mark.parametrize(
        "test_description, tool_response, nums_of_chunks, expected_chunks",
        [
            (
                "should create chunks correctly from list with exact division",
                [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
                2,
                [
                    Document(page_content="{'id': 1}\n\n{'id': 2}"),
                    Document(page_content="{'id': 3}\n\n{'id': 4}"),
                ],
            ),
            (
                "should create chunks correctly from list with inexact division",
                [{"id": 1}, {"id": 2}, {"id": 3}],
                2,
                [
                    Document(page_content="{'id': 1}\n\n{'id': 2}"),
                    Document(page_content="{'id': 3}"),
                ],
            ),
            (
                "should handle single item list",
                [{"id": 1}],
                2,
                [Document(page_content="{'id': 1}")],
            ),
            (
                "should handle empty list",
                [],
                2,
                [],
            ),
        ],
    )
    def test_create_chunks_from_list(
        self,
        summarizer,
        test_description,
        tool_response,
        nums_of_chunks,
        expected_chunks,
    ):
        # given
        # Convert the list items to string representation for comparison
        for i, item in enumerate(tool_response):
            tool_response[i] = str(item)

        # when
        chunks = summarizer._create_chunks_from_list(tool_response, nums_of_chunks)

        # then
        assert len(chunks) == len(expected_chunks)
        for i, chunk in enumerate(chunks):
            assert chunk.page_content == expected_chunks[i].page_content

    @pytest.mark.asyncio
    @patch("agents.common.chunk_summarizer.ainvoke_chain", new_callable=AsyncMock)
    async def test_summarize_tool_response(self, mock_ainvoke_chain, summarizer):
        # given
        tool_response = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]
        user_query = "sample query"
        config = {"config_key": "config_value"}
        nums_of_chunks = 2

        mock_chain = AsyncMock()
        summarizer._create_chain = Mock(return_value=mock_chain)

        # Mock response objects with content attribute
        mock_response1 = Mock()
        mock_response1.content = "Summary 1"
        mock_response2 = Mock()
        mock_response2.content = "Summary 2"

        mock_ainvoke_chain.side_effect = [mock_response1, mock_response2]

        summarizer._create_chunks_from_list = Mock(
            return_value=[
                Document(page_content="Chunk 1"),
                Document(page_content="Chunk 2"),
            ]
        )

        result = await summarizer.summarize_tool_response(
            tool_response, user_query, config, nums_of_chunks
        )

        summarizer._create_chunks_from_list.assert_called_once_with(
            [tool_response], nums_of_chunks
        )

        assert mock_ainvoke_chain.call_count == nums_of_chunks

        # Check first ainvoke_chain call
        mock_ainvoke_chain.assert_any_call(
            mock_chain,
            {"tool_response_chunk": "Chunk 1"},
            config=config,
        )

        # Check second ainvoke_chain call
        mock_ainvoke_chain.assert_any_call(
            mock_chain,
            {"tool_response_chunk": "Chunk 2"},
            config=config,
        )

        assert result == "Summary 1\n\nSummary 2"

    @pytest.mark.asyncio
    async def test_summarize_tool_response_with_empty_chunks(self, summarizer):
        # given
        tool_response = []
        user_query = "sample query"
        config = {"config_key": "config_value"}
        nums_of_chunks = 2

        # Create spy for _create_chunks_from_list
        summarizer._create_chunks_from_list = Mock(return_value=[])

        # when
        result = await summarizer.summarize_tool_response(
            tool_response, user_query, config, nums_of_chunks
        )

        # then
        summarizer._create_chunks_from_list.assert_called_once_with(
            [tool_response], nums_of_chunks
        )
        assert result == ""
