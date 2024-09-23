import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.constants import END

from agents.common.constants import (
    COMMON,
    CONTINUE,
    EXIT,
    FINALIZER,
    PLANNER,
)
from agents.common.data import Message
from agents.common.state import AgentState, SubTask, UserInput
from agents.graph import KymaGraph
from agents.k8s.agent import K8S_AGENT
from agents.kyma.agent import KYMA_AGENT
from utils.models import IModel


@pytest.fixture
def mock_model():
    return Mock(spec=IModel)


@pytest.fixture
def mock_memory():
    return Mock()


@pytest.fixture
def mock_graph():
    return Mock()


@pytest.fixture
def kyma_graph(mock_model, mock_memory, mock_graph):
    with patch.object(KymaGraph, "_build_graph", return_value=mock_graph):
        return KymaGraph(mock_model, mock_memory)


def create_messages_json(content, role, node) -> str:
    json_str = f"""{{"content": "{content}", "additional_kwargs": {{}}, "response_metadata": {{}}, "type": "{role}", "name": null, "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}}"""  # noqa
    return json_str


class TestKymaGraph:

    @pytest.mark.parametrize(
        "description, input_query, plan_content, expected_output, expected_error",
        [
            (
                "Plans multiple subtasks successfully",
                "How do I deploy a Kyma function?",
                '{"subtasks": [{"description": "Explain Kyma function deployment", "assigned_to": "KymaAgent"},'
                '{"description": "Explain K8s deployment", "assigned_to": "KubernetesAgent"}]}',
                {
                    "subtasks": [
                        SubTask(
                            description="Explain Kyma function deployment",
                            assigned_to=KYMA_AGENT,
                        ),
                        SubTask(
                            description="Explain K8s deployment",
                            assigned_to=K8S_AGENT,
                        ),
                    ],
                    "messages": [
                        AIMessage(
                            content="Task decomposed into subtasks and assigned to agents: "
                            '[{"description": "Explain Kyma function deployment", "assigned_to": "KymaAgent", '
                            '"status": "pending", "result": null}, {"description": "Explain K8s deployment", '
                            '"assigned_to": "KubernetesAgent", "status": "pending", "result": null}]',
                            name=PLANNER,
                        )
                    ],
                    "error": None,
                    "final_response": None,
                    "next": CONTINUE,
                },
                None,
            ),
            (
                "Plans a single subtask successfully",
                "What is a Kubernetes pod?",
                '{"subtasks": [{"description": "Explain Kubernetes pod concept", "assigned_to": "KubernetesAgent"}]}',
                {
                    "subtasks": [
                        SubTask(
                            description="Explain Kubernetes pod concept",
                            assigned_to="KubernetesAgent",
                        )
                    ],
                    "messages": [
                        AIMessage(
                            content="Task decomposed into subtasks and assigned to agents: "
                            '[{"description": "Explain Kubernetes pod concept", "assigned_to": "KubernetesAgent", '
                            '"status": "pending", "result": null}]',
                            name=PLANNER,
                        )
                    ],
                    "error": None,
                    "final_response": None,
                    "next": CONTINUE,
                },
                None,
            ),
            (
                "Exits with error if no subtasks are returned",
                "What is a Kubernetes pod?",
                '{"subtasks": []}',
                {
                    "subtasks": None,
                    "messages": [],
                    "final_response": None,
                    "next": EXIT,
                    "error": "No subtasks are created for the given query: What is a Kubernetes pod?",
                },
                None,
            ),
            (
                "Exits immediately by answering for the general query",
                "Write a hello world python code?",
                '{"response": "Here is the hellow world python code: print(\'Hello, World!\')"}',
                {
                    "subtasks": None,
                    "messages": [
                        AIMessage(
                            content="Here is the hellow world python code: print('Hello, World!')",
                            name=PLANNER,
                        )
                    ],
                    "error": None,
                    "final_response": "Here is the hellow world python code: print('Hello, World!')",
                    "next": EXIT,
                },
                None,
            ),
            (
                "Exits immediately for the general query even if llm doesn't return response attribute",
                "Write a hello world python code?",
                "Here is the hellow world python code: print('Hello, World!')",
                {
                    "subtasks": None,
                    "messages": [
                        AIMessage(
                            content="Here is the hellow world python code: print('Hello, World!')",
                            name=PLANNER,
                        )
                    ],
                    "error": None,
                    "final_response": "Here is the hellow world python code: print('Hello, World!')",
                    "next": EXIT,
                },
                None,
            ),
            (
                "Exits of error occurs in planning",
                "What is a Kubernetes service?",
                '{"subtasks": [{"description": "Explain Kubernetes service", "assigned_to": "KubernetesAgent"}]}',
                {
                    "subtasks": None,
                    "messages": [],
                    "error": "fake error",
                    "final_response": None,
                    "next": EXIT,
                },
                "fake error",
            ),
        ],
    )
    def test_plan(
        self,
        kyma_graph,
        description,
        input_query,
        plan_content,
        expected_output,
        expected_error,
    ):
        state = AgentState(messages=[HumanMessage(content=input_query)])

        mock_planner_chain = Mock()

        if expected_error:
            mock_planner_chain.invoke.side_effect = Exception(expected_error)
        else:
            mock_planner_chain.invoke.return_value.content = plan_content

        with patch.object(
            kyma_graph, "_create_planner_chain", return_value=mock_planner_chain
        ):
            result = kyma_graph._plan(state)

        assert result == expected_output

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
                    "error": "Error in common node: Test error",
                    "next": EXIT,
                },
                "Error in common node: Test error",
            ),
        ],
    )
    def test_common_node(
        self,
        kyma_graph,
        description,
        subtasks,
        messages,
        chain_response,
        expected_output,
        expected_error,
    ):
        state = AgentState(subtasks=subtasks, messages=messages)

        mock_chain = Mock()

        if expected_error:
            mock_chain.invoke.side_effect = Exception(expected_error)
        else:
            mock_chain.invoke.return_value.content = chain_response

        with patch.object(kyma_graph, "_common_node_chain", return_value=mock_chain):
            result = kyma_graph.common_node(state)

        assert result == expected_output
        if chain_response:
            mock_chain.invoke.assert_called_once()
            assert (
                subtasks[0].assigned_to == COMMON and subtasks[0].status == "completed"
            )

    @pytest.mark.parametrize(
        "description, input_query, conversation_messages, final_response_content, expected_output, expected_error",
        [
            (
                "Generates final response successfully",
                "How do I deploy a Kyma function?",
                [
                    HumanMessage(content="How do I deploy a Kyma function?"),
                    AIMessage(
                        content="To deploy a Kyma function, you need to...",
                        name="KymaAgent",
                    ),
                    AIMessage(
                        content="In Kubernetes, deployment involves...",
                        name="KubernetesAgent",
                    ),
                ],
                "To deploy a Kyma function, follow these steps: 1. Create a function file. "
                "2. Use the Kyma CLI to deploy. 3. Verify the deployment in the Kyma dashboard.",
                {
                    "final_response": "To deploy a Kyma function, follow these steps: "
                    "1. Create a function file. 2. Use the Kyma CLI to deploy. "
                    "3. Verify the deployment in the Kyma dashboard.",
                    "messages": [
                        AIMessage(
                            content="To deploy a Kyma function, follow these steps: "
                            "1. Create a function file. 2. Use the Kyma CLI to deploy. "
                            "3. Verify the deployment in the Kyma dashboard.",
                            name=FINALIZER,
                        )
                    ],
                    "next": END,
                },
                None,
            ),
            (
                "Generates empty final response",
                "What is Kubernetes?",
                [
                    HumanMessage(content="What is Kubernetes?"),
                    AIMessage(
                        content="Kubernetes is a container orchestration platform.",
                        name="KubernetesAgent",
                    ),
                ],
                "",
                {
                    "final_response": "",
                    "messages": [
                        AIMessage(
                            content="",
                            name=FINALIZER,
                        )
                    ],
                    "next": END,
                },
                None,
            ),
            (
                "Handles exception during final response generation",
                "What is Kubernetes?",
                [
                    HumanMessage(content="What is Kubernetes?"),
                    AIMessage(
                        content="Kubernetes is a container orchestration platform.",
                        name="KubernetesAgent",
                    ),
                ],
                None,
                {
                    "error": "Error in finalizer node: Test error",
                    "next": EXIT,
                },
                "Error in finalizer node: Test error",
            ),
        ],
    )
    def test_generate_final_response(
        self,
        kyma_graph,
        description,
        input_query,
        conversation_messages,
        final_response_content,
        expected_output,
        expected_error,
    ):
        state = AgentState(
            messages=conversation_messages, input=UserInput(query=input_query)
        )

        mock_final_response_chain = Mock()
        if expected_error:
            mock_final_response_chain.invoke.side_effect = Exception(expected_error)
        else:
            mock_final_response_chain.invoke.return_value.content = (
                final_response_content
            )

        with patch.object(
            kyma_graph, "_final_response_chain", return_value=mock_final_response_chain
        ):
            result = kyma_graph.generate_final_response(state)

        assert result == expected_output
        mock_final_response_chain.invoke.assert_called_once_with(
            {"messages": conversation_messages}
        )

    @pytest.fixture
    def mock_kyma_graph(self):
        mock_graph = MagicMock()
        mock_graph.astream.return_value = AsyncMock()
        mock_graph.astream.return_value.__aiter__.return_value = [
            "chunk1",
            "chunk2",
            "chunk3",
        ]
        with patch("services.conversation.KymaGraph", return_value=kyma_graph) as mock:
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
    async def test_astream_second(
        self,
        kyma_graph,
        description,
        conversation_id,
        message,
        mock_chunks,
        expected_output,
        expected_error,
    ):
        # Create an async generator function to mock the graph's astream method
        async def mock_astream(*args, **kwargs):
            if isinstance(mock_chunks, Exception):
                raise mock_chunks
            for chunk in mock_chunks:
                yield chunk

        # Mock the graph's astream method with our async generator function
        kyma_graph.graph.astream = mock_astream

        if expected_error:
            with pytest.raises(Exception) as exc_info:
                async for _ in kyma_graph.astream(conversation_id, message):
                    pass
            assert str(exc_info.value) == expected_error
        else:
            result = []
            async for chunk in kyma_graph.astream(conversation_id, message):
                result.append(chunk)

            def compare_json(json_str1, json_str2):
                obj1 = json.loads(json_str1)
                obj2 = json.loads(json_str2)
                return obj1 == obj2

            assert result == expected_output
