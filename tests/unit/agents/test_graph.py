from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import StateSnapshot

from agents.common.constants import COMMON, GATEKEEPER
from agents.common.data import Message
from agents.common.state import CompanionState, GatekeeperResponse, SubTask
from agents.graph import CompanionGraph
from agents.supervisor.agent import SUPERVISOR
from services.k8s import IK8sClient
from utils.models.factory import IModel, ModelType


@pytest.fixture
def mock_models():
    gpt40_mini = MagicMock(spec=IModel)
    gpt40_mini.name = ModelType.GPT4O_MINI

    gpt40 = MagicMock(spec=IModel)
    gpt40.name = ModelType.GPT4O

    text_embedding_3_large = MagicMock(spec=Embeddings)
    text_embedding_3_large.name = ModelType.TEXT_EMBEDDING_3_LARGE

    return {
        ModelType.GPT4O_MINI: gpt40_mini,
        ModelType.GPT4O: gpt40,
        ModelType.TEXT_EMBEDDING_3_LARGE: text_embedding_3_large,
    }


@pytest.fixture
def mock_memory():
    return Mock()


@pytest.fixture
def mock_planner_chain():
    return Mock()


@pytest.fixture
def mock_common_chain():
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_gatekeeper_chain():
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_graph():
    return Mock()


@pytest.fixture
def companion_graph(
    mock_models,
    mock_memory,
    mock_graph,
    mock_planner_chain,
    mock_common_chain,
    mock_gatekeeper_chain,
):
    with (
        patch.object(
            CompanionGraph, "_create_common_chain", return_value=mock_common_chain
        ),
        patch.object(
            CompanionGraph,
            "_create_gatekeeper_chain",
            return_value=mock_gatekeeper_chain,
        ),
        patch.object(CompanionGraph, "_build_graph", return_value=mock_graph),
        patch("agents.graph.KymaAgent", return_value=Mock()),
    ):
        graph = CompanionGraph(mock_models, mock_memory)
        graph._invoke_common_node = AsyncMock()
        graph._invoke_gatekeeper_node = AsyncMock()
        return graph


def create_messages_json(content, role, node) -> str:
    json_str = f"""{{"content": "{content}", "additional_kwargs": {{}}, "response_metadata": {{}}, "type": "{role}", "name": null, "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}}"""  # noqa
    return json_str


class TestCompanionGraph:
    @pytest.mark.asyncio
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
                        task_title="Explain Python",
                    )
                ],
                [HumanMessage(content="What is Java?")],
                "Python is a high-level programming language. Java is a general-purpose programming language.",
                {
                    "messages": [
                        AIMessage(
                            content="Python is a high-level programming language. Java is a general-purpose programming language.",
                            additional_kwargs={},
                            response_metadata={},
                            name="Common",
                        )
                    ],
                    "subtasks": [
                        SubTask(
                            description="Explain Python",
                            task_title="Explain Python",
                            assigned_to="Common",
                            status="completed",
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
                        task_title="Explain Python",
                        assigned_to=COMMON,
                        status="pending",
                    ),
                    SubTask(
                        description="Explain Java",
                        task_title="Explain Java",
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
                    "subtasks": [
                        SubTask(
                            description="Explain Python",
                            task_title="Explain Python",
                            assigned_to="Common",
                            status="completed",
                        ),
                        SubTask(
                            description="Explain Java",
                            task_title="Explain Java",
                            assigned_to="Common",
                            status="pending",
                        ),
                    ],
                },
                None,
            ),
            (
                "Returns message when all subtasks are already completed",
                [
                    SubTask(
                        description="Explain Python",
                        task_title="Explain Python",
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
                    "subtasks": [
                        SubTask(
                            description="Explain Python",
                            task_title="Explain Python",
                            assigned_to="Common",
                            status="completed",
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
                        task_title="Explain Python",
                        assigned_to=COMMON,
                        status="pending",
                    )
                ],
                [HumanMessage(content="What is Java?")],
                None,
                {
                    "messages": [
                        AIMessage(
                            content="Sorry, I am unable to process the request.",
                            name=COMMON,
                        )
                    ],
                    "subtasks": [
                        SubTask(
                            description="Explain Python",
                            task_title="Explain Python",
                            assigned_to="Common",
                            status="pending",
                        )
                    ],
                },
                "Error in common node: Test error",
            ),
        ],
    )
    async def test_common_node(
        self,
        companion_graph,
        description,
        subtasks,
        messages,
        chain_response,
        expected_output,
        expected_error,
    ):
        state = CompanionState(subtasks=subtasks, messages=messages)

        if expected_error:
            companion_graph._invoke_common_node.side_effect = Exception(expected_error)
        else:
            companion_graph._invoke_common_node.return_value = chain_response

        result = await companion_graph._common_node(state)
        assert result == expected_output

        if chain_response:
            companion_graph._invoke_common_node.assert_awaited_once_with(
                state, subtasks[0].description
            )
            assert subtasks[0].status == "completed"
        elif expected_error:
            # if error occurs, return message with error
            companion_graph._invoke_common_node.assert_awaited_once_with(
                state, subtasks[0].description
            )
            # Verify subtask remains pending after error
            assert subtasks[0].status == "pending"
            assert subtasks[0].assigned_to == COMMON
        else:
            # if all subtasks are completed, no need call LLM
            assert subtasks[0].status == "completed"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case, messages, chain_response, expected_output, expected_error",
        [
            (
                "Direct response, mark next == __end__",
                [HumanMessage(content="What are Java and Python?")],
                '{"direct_response" :"Python is a high-level programming language. Java is a general-purpose programming language.", "forward_query" : false}',
                {
                    "messages": [
                        AIMessage(
                            content="Python is a high-level programming language. "
                            "Java is a general-purpose programming language.",
                            name=GATEKEEPER,
                        )
                    ],
                    "subtasks": [],
                    "next": "__end__",
                },
                None,
            ),
            (
                "No direct response, Forward query to supervisor",
                [HumanMessage(content="What is Kyma?")],
                '{"direct_response" :"", "forward_query" : true}',
                {
                    "subtasks": [],
                    "next": SUPERVISOR,
                },
                None,
            ),
            (
                "Handles exception during gatekeeper execution",
                [HumanMessage(content="What is Java?")],
                None,
                {
                    "messages": [
                        AIMessage(
                            content="Sorry, I am unable to process the request.",
                            name=GATEKEEPER,
                        )
                    ],
                    "subtasks": [],
                    "next": "__end__",
                },
                "Error in common node: Test error",
            ),
        ],
    )
    async def test_gatekeeper_node(
        self,
        companion_graph,
        test_case,
        messages,
        chain_response,
        expected_output,
        expected_error,
    ):
        # Given
        state = CompanionState(subtasks=[], messages=messages)

        if expected_error:
            companion_graph._invoke_gatekeeper_node.side_effect = Exception(
                expected_error
            )
        else:
            companion_graph._invoke_gatekeeper_node.return_value = (
                GatekeeperResponse.model_validate_json(chain_response)
            )

        # When
        result = await companion_graph._gatekeeper_node(state)
        assert result == expected_output, test_case

        # Then
        if chain_response:
            companion_graph._invoke_gatekeeper_node.assert_awaited_once_with(state)
        elif expected_error:
            # if error occurs, return message with error
            companion_graph._invoke_gatekeeper_node.assert_awaited_once_with(state)

    @pytest.fixture
    def mock_companion_graph(self):
        mock_graph = MagicMock()
        mock_graph.astream.return_value = AsyncMock()
        mock_graph.astream.return_value.__aiter__.return_value = [
            "chunk1",
            "chunk2",
            "chunk3",
        ]
        with patch(
            "services.conversation.CompanionGraph", return_value=companion_graph
        ) as mock:
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
                    f'{{"Planner": {create_messages_json("Query is decomposed into subtasks", "ai", "Planner")}}}',
                    f'{{"Supervisor": {create_messages_json("next is KymaAgent", "ai", "Supervisor")}}}',
                    f'{{"KymaAgent": {
                        create_messages_json(
                            "You can deploy a Kyma function by following these steps", "ai", "KymaAgent"
                        )
                    }}}',
                    f'{{"Supervisor": {create_messages_json("next is KubernetesAgent", "ai", "Supervisor")}}}',
                    f'{{"KubernetesAgent": {
                        create_messages_json("You can deploy a k8s app by following these steps", "ai", "Supervisor")
                    }}}',
                    f'{{"Exit": {create_messages_json("final response", "ai", "Exit")}}}',
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
            (
                "Should include resource info when non-empty",
                "conv_456",
                Message(
                    query="What is Kubernetes?",
                    resource_kind="Cluster",
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
                "Should not include resource info when empty",
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
        mock_k8s_client = Mock(spec=IK8sClient)
        mock_k8s_client.get_api_server.return_value = "url.cluster_url.test_url"

        # Create an async generator function to mock the graph's astream method
        async def mock_astream(*args, **kwargs):
            first_message = kwargs["input"]["messages"][0]
            if (
                message.namespace == ""
                and message.resource_kind == ""
                and message.resource_name == ""
                and message.resource_api_version == ""
            ):
                if not isinstance(first_message, HumanMessage):
                    raise Exception(
                        "The first message should be a HumanMessage when resource info is empty."
                    )
            else:
                if not isinstance(first_message, SystemMessage):
                    raise Exception(
                        "The first message should be a SystemMessage when resource_name info is non-empty."
                    )
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

            assert result == expected_output

    def test_agent_initialization(self, companion_graph, mock_models, mock_memory):
        with (
            patch("agents.graph.KymaAgent") as mock_kyma_cls,
            patch("agents.graph.KubernetesAgent") as mock_k8s_cls,
            patch("agents.graph.SupervisorAgent") as mock_supervisor_cls,
            patch.object(CompanionGraph, "_build_graph") as mock_build_graph,
        ):
            CompanionGraph(mock_models, mock_memory)

            # Verify KymaAgent was constructed with models
            mock_kyma_cls.assert_called_once_with(mock_models)

            # Verify KubernetesAgent was constructed with GPT4O model
            mock_k8s_cls.assert_called_once_with(mock_models[ModelType.GPT4O])

            # Verify SupervisorAgent was constructed with correct arguments
            mock_supervisor_cls.assert_called_once_with(
                mock_models,
                members=["KymaAgent", "KubernetesAgent", "Common"],
            )

            mock_build_graph.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "conversation_id, given_latest_state_values, expected_output",
        [
            # test case when the latest state values is empty.
            (
                "e9974a27-048e-4e65-b4ed-a02d201465a6",
                {},
                [],
            ),
            # test case when the latest state values do not have messages key.
            (
                "e9974a27-048e-4e65-b4ed-a02d201465a6",
                {
                    "dummy_key": "dummy_value",
                },
                [],
            ),
            # test case when the latest state values have messages.
            (
                "e9974a27-048e-4e65-b4ed-a02d201465a6",
                {
                    "messages": [
                        AIMessage(content="Message 1"),
                        AIMessage(content="Message 2"),
                    ],
                },
                [
                    AIMessage(content="Message 1"),
                    AIMessage(content="Message 2"),
                ],
            ),
        ],
    )
    async def test_aget_messages(
        self,
        companion_graph,
        conversation_id,
        given_latest_state_values,
        expected_output,
    ):
        # given
        given_latest_state = StateSnapshot(
            values=given_latest_state_values,
            next=(),
            config=RunnableConfig(),
            tasks=(),
            metadata=None,
            created_at=None,
            parent_config=None,
        )
        companion_graph.graph.aget_state = AsyncMock(return_value=given_latest_state)

        # when
        result = await companion_graph.aget_messages(conversation_id)

        # then
        assert result == expected_output
        companion_graph.graph.aget_state.assert_called_once_with(
            {
                "configurable": {
                    "thread_id": conversation_id,
                },
            }
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "conversation_id, state_values, expected_owner",
        [
            (
                "conversation1",
                {"thread_owner": "user1"},
                "user1",
            ),
            (
                "conversation2",
                {"thread_owner": ""},
                None,
            ),
            (
                "conversation3",
                {},
                None,
            ),
        ],
    )
    async def test_aget_thread_owner(
        self, companion_graph, conversation_id, state_values, expected_owner
    ):
        # Given
        state_snapshot = StateSnapshot(
            values=state_values,
            next=(),
            config=RunnableConfig(),
            tasks=(),
            metadata=None,
            created_at=None,
            parent_config=None,
        )
        companion_graph.graph.aget_state = AsyncMock(return_value=state_snapshot)

        # When
        result = await companion_graph.aget_thread_owner(conversation_id)

        # Then
        assert result == expected_owner
        companion_graph.graph.aget_state.assert_called_once_with(
            {
                "configurable": {
                    "thread_id": conversation_id,
                },
            }
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "conversation_id, user_identifier, initial_state_values, expected_state_values",
        [
            (
                "conversation1",
                "user1",
                {"thread_owner": ""},
                {"thread_owner": "user1"},
            ),
            (
                "conversation2",
                "user2",
                {},
                {"thread_owner": "user2"},
            ),
        ],
    )
    async def test_aupdate_thread_owner(
        self,
        companion_graph,
        conversation_id,
        user_identifier,
        initial_state_values,
        expected_state_values,
    ):
        # Given
        initial_state_snapshot = StateSnapshot(
            values=initial_state_values,
            next=(),
            config=RunnableConfig(),
            tasks=(),
            metadata=None,
            created_at=None,
            parent_config=None,
        )
        companion_graph.graph.aget_state = AsyncMock(
            return_value=initial_state_snapshot
        )
        companion_graph.graph.aupdate_state = AsyncMock()

        # When
        await companion_graph.aupdate_thread_owner(conversation_id, user_identifier)

        # Then
        companion_graph.graph.aupdate_state.assert_called_once_with(
            {
                "configurable": {
                    "thread_id": conversation_id,
                },
            },
            expected_state_values,
        )
