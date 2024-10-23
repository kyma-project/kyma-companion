import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.common.constants import COMMON
from agents.common.data import Message
from agents.common.state import AgentState, SubTask
from agents.graph import CompanionGraph
from utils.models import LLM, IModel


@pytest.fixture
def mock_models():
    return {
        LLM.GPT4O_MINI: MagicMock(spec=IModel),
        LLM.GPT4O: MagicMock(spec=IModel),
    }


@pytest.fixture
def mock_memory():
    return Mock()


@pytest.fixture
def mock_planner_chain():
    return Mock()


@pytest.fixture
def mock_common_chain():
    return Mock()


@pytest.fixture
def mock_graph():
    return Mock()


@pytest.fixture
def companion_graph(
    mock_models, mock_memory, mock_graph, mock_planner_chain, mock_common_chain
):
    with (
        patch.object(CompanionGraph, "_create_common_chain", return_value=mock_common_chain),
        patch.object(CompanionGraph, "_build_graph", return_value=mock_graph),
    ):
        return CompanionGraph(mock_models, mock_memory)


def create_messages_json(content, role, node) -> str:
    json_str = f"""{{"content": "{content}", "additional_kwargs": {{}}, "response_metadata": {{}}, "type": "{role}", "name": null, "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}}"""  # noqa
    return json_str


class TestCompanionGraph:

    @pytest.mark.parametrize(
        "description, subtasks, messages, chain_response, expected_output, expected_error",
        [
            (
                "Completes a single subtask successfully",
                [
                    SubTask(
                        description="Explain Python",
                        assigned_to=COMMON,
                        status="pending",
                    )
                ],
                [HumanMessage(content="What is Java?")],
                "Python is a high-level programming language. Java is a general-purpose programming language.",
                {
                    "messages": [
                        AIMessage(
                            content="Python is a high-level programming language. "
                            "Java is a general-purpose programming language.",
                            name=COMMON,
                        )
                    ],
                },
                None,
            ),
            (
                "Completes multiple subtasks successfully",
                [
                    SubTask(
                        description="Explain Python",
                        assigned_to=COMMON,
                        status="pending",
                    ),
                    SubTask(
                        description="Explain Java",
                        assigned_to=COMMON,
                        status="pending",
                    ),
                ],
                [HumanMessage(content="What are Java and Python?")],
                "Python is a high-level programming language. Java is a general-purpose programming language.",
                {
                    "messages": [
                        AIMessage(
                            content="Python is a high-level programming language. "
                            "Java is a general-purpose programming language.",
                            name=COMMON,
                        )
                    ],
                },
                None,
            ),
            (
                "Returns message when all subtasks are already completed",
                [
                    SubTask(
                        description="Explain Python",
                        assigned_to=COMMON,
                        status="completed",
                    )
                ],
                [HumanMessage(content="What is Java?")],
                None,
                {
                    "messages": [
                        AIMessage(
                            content="All my subtasks are already completed.",
                            name=COMMON,
                        )
                    ],
                },
                None,
            ),
            (
                "Handles exception during subtask execution",
                [
                    SubTask(
                        description="Explain Python",
                        assigned_to=COMMON,
                        status="pending",
                    )
                ],
                [HumanMessage(content="What is Java?")],
                None,
                {
                    'messages': [
                        AIMessage(
                            content='Sorry, the common agent is unable to process the request.',
                            name='Common'
                        )
                    ]
                },
                "Error in common node: Test error",
            ),
        ],
    )
    def test_common_node(
        self,
        companion_graph,
        description,
        subtasks,
        messages,
        chain_response,
        expected_output,
        expected_error,
        mock_common_chain,
    ):
        state = AgentState(subtasks=subtasks, messages=messages)

        if expected_error:
            mock_common_chain.invoke.side_effect = Exception(expected_error)
        else:
            mock_common_chain.invoke.return_value.content = chain_response

        result = companion_graph._common_node(state)
        assert result == expected_output
        if chain_response:
            mock_common_chain.invoke.assert_called_once()
            assert (
                subtasks[0].assigned_to == COMMON and subtasks[0].status == "completed"
            )

    @pytest.fixture
    def mock_companion_graph(self):
        mock_graph = MagicMock()
        mock_graph.astream.return_value = AsyncMock()
        mock_graph.astream.return_value.__aiter__.return_value = [
            "chunk1",
            "chunk2",
            "chunk3",
        ]
        with patch("services.conversation.CompanionGraph", return_value=companion_graph) as mock:
            yield mock

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "description, conversation_id, message, mock_chunks, expected_output, expected_error",
        [
            (
                "Successful stream with multiple chunks",
                "conv_123",
                Message(
                    query="How do I deploy a Kyma function?",
                    resource_kind="",
                    resource_api_version="",
                    resource_name="",
                    namespace="",
                ),
                [
                    {"Planner": AIMessage(content="Query is decomposed into subtasks")},
                    {"Supervisor": AIMessage(content="next is KymaAgent")},
                    {
                        "KymaAgent": AIMessage(
                            content="You can deploy a Kyma function by following these steps"
                        )
                    },
                    {"Supervisor": AIMessage(content="next is KubernetesAgent")},
                    {
                        "KubernetesAgent": AIMessage(
                            content="You can deploy a k8s app by following these steps"
                        )
                    },
                    {"Exit": AIMessage(content="final response")},
                ],
                [
                    f'{{"Planner": {create_messages_json("Query is decomposed into subtasks",
                                                             "ai", "Planner")}}}',
                    f'{{"Supervisor": {create_messages_json("next is KymaAgent",
                                                                "ai", "Supervisor")}}}',
                    f'{{"KymaAgent": {create_messages_json(
                            "You can deploy a Kyma function by following these steps",
                            "ai", "KymaAgent")}}}',
                    f'{{"Supervisor": {create_messages_json("next is KubernetesAgent",
                                                                "ai", "Supervisor")}}}',
                    f'{{"KubernetesAgent": {create_messages_json("You can deploy a k8s app by following these steps",
                                                                     "ai", "Supervisor")}}}',
                    f'{{"Exit": {create_messages_json("final response",
                                                          "ai", "Exit")}}}',
                ],
                None,
            ),
            (
                "Successful stream with single chunk",
                "conv_456",
                Message(
                    query="What is Kubernetes?",
                    resource_kind="",
                    resource_api_version="",
                    resource_name="",
                    namespace="",
                ),
                [
                    {"Exit": AIMessage(content="final response")},
                ],
                [
                    f'{{"Exit": {create_messages_json("final response", "ai", "Exit")}}}',
                ],
                None,
            ),
            (
                "Empty response",
                "conv_789",
                Message(
                    query="",
                    resource_kind="",
                    resource_api_version="",
                    resource_name="",
                    namespace="",
                ),
                [{"__end__": True}],
                [],
                None,
            ),
            (
                "Error in graph execution",
                "conv_error",
                Message(
                    query="Cause an error",
                    resource_kind="",
                    resource_api_version="",
                    resource_name="",
                    namespace="",
                ),
                Exception("Graph execution failed"),
                None,
                "Graph execution failed",
            ),
        ],
    )
    async def test_astream(
        self,
        companion_graph,
        description,
        conversation_id,
        message,
        mock_chunks,
        expected_output,
        expected_error,
    ):
        # Given:
        mock_k8s_client = Mock()

        # Create an async generator function to mock the graph's astream method
        async def mock_astream(*args, **kwargs):
            if isinstance(mock_chunks, Exception):
                raise mock_chunks
            for chunk in mock_chunks:
                yield chunk

        # Mock the graph's astream method with our async generator function
        companion_graph.graph.astream = mock_astream

        if expected_error:
            with pytest.raises(Exception) as exc_info:
                async for _ in companion_graph.astream(
                    conversation_id, message, mock_k8s_client
                ):
                    pass
            assert str(exc_info.value) == expected_error
        else:
            result = []
            async for chunk in companion_graph.astream(
                conversation_id, message, mock_k8s_client
            ):
                result.append(chunk)

            def compare_json(json_str1, json_str2):
                obj1 = json.loads(json_str1)
                obj2 = json.loads(json_str2)
                return obj1 == obj2

            assert result == expected_output
