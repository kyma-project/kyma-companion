from unittest.mock import MagicMock, Mock, patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.constants import END

from agents.common.constants import COMMON, PLANNER
from agents.common.state import CompanionState, SubTask
from agents.k8s.agent import K8S_AGENT
from agents.kyma.agent import KYMA_AGENT
from agents.supervisor.agent import FINALIZER, ROUTER, SupervisorAgent
from agents.supervisor.state import SupervisorState
from utils.models.factory import IModel, ModelType


@pytest.fixture
def mock_models():
    return {
        ModelType.GPT4O_MINI: MagicMock(spec=IModel),
        ModelType.GPT4O: MagicMock(spec=IModel),
        ModelType.TEXT_EMBEDDING_3_LARGE: MagicMock(spec=Embeddings),
    }


class TestSupervisorAgent:

    @pytest.fixture
    def supervisor_agent(self, mock_models):
        agent = SupervisorAgent(
            models=mock_models, members=[K8S_AGENT, KYMA_AGENT, COMMON, FINALIZER]
        )  # noqa
        agent.supervisor_chain = Mock()
        agent._planner_chain = Mock()
        return agent  # noqa

    @pytest.mark.parametrize(
        "subtasks, messages, expected_next, expected_subtasks, expected_error",
        [
            (
                [
                    SubTask(
                        description="Task 1", assigned_to=K8S_AGENT, status="pending"
                    ),
                    SubTask(
                        description="Task 2", assigned_to=KYMA_AGENT, status="pending"
                    ),
                ],
                [
                    HumanMessage(content="Test message 1"),
                    AIMessage(content="Test message 2"),
                ],
                K8S_AGENT,
                [
                    SubTask(
                        description="Task 1", assigned_to=K8S_AGENT, status="pending"
                    ),
                    SubTask(
                        description="Task 2", assigned_to=KYMA_AGENT, status="pending"
                    ),
                ],
                None,
            ),
            (
                [
                    SubTask(
                        description="Task 2",
                        assigned_to=KYMA_AGENT,
                        status="in_progress",
                    )
                ],
                [AIMessage(content="Fake message")],
                KYMA_AGENT,
                [
                    SubTask(
                        description="Task 2",
                        assigned_to=KYMA_AGENT,
                        status="in_progress",
                    )
                ],
                None,
            ),
            (
                [
                    SubTask(
                        description="Task 3", assigned_to=K8S_AGENT, status="completed"
                    )
                ],
                [],
                FINALIZER,
                [
                    SubTask(
                        description="Task 3", assigned_to=K8S_AGENT, status="completed"
                    )
                ],
                None,
            ),
        ],
    )
    def test_agent_route(
        self,
        supervisor_agent,
        subtasks,
        messages,
        expected_next,
        expected_subtasks,
        expected_error,
    ):
        # Setup
        state = CompanionState(messages=messages, subtasks=subtasks)

        # Execute
        route_node = supervisor_agent._route
        result = route_node(state)

        if expected_error:
            assert result["messages"][0].content == expected_error
        else:
            assert result["next"] == expected_next
            assert "error" not in result

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
                "To deploy a Kyma function, follow these steps: "
                "1. Create a function file. "
                "2. Use the Kyma CLI to deploy. "
                "3. Verify the deployment in the Kyma dashboard.",
                {
                    "messages": [
                        AIMessage(
                            content="To deploy a Kyma function, follow these steps: "
                            "1. Create a function file. "
                            "2. Use the Kyma CLI to deploy. "
                            "3. Verify the deployment in the Kyma dashboard.",
                            name="Finalizer",
                        )
                    ],
                    "next": "__end__",
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
                    "messages": [AIMessage(content="", name="Finalizer")],
                    "next": "__end__",
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
                    "messages": [
                        AIMessage(
                            content="Sorry, I encountered an error while processing the request. "
                            "Error: Error in finalizer node: Test error",
                            name="Finalizer",
                        )
                    ]
                },
                "Error in finalizer node: Test error",
            ),
        ],
    )
    def test_agent_generate_final_response(
        self,
        supervisor_agent,
        description,
        input_query,
        conversation_messages,
        final_response_content,
        expected_output,
        expected_error,
    ):
        state = SupervisorState(messages=conversation_messages)

        mock_final_response_chain = Mock()
        if expected_error:
            mock_final_response_chain.invoke.side_effect = Exception(expected_error)
        else:
            mock_final_response_chain.invoke.return_value.content = (
                final_response_content
            )

        with patch.object(
            supervisor_agent,
            "_final_response_chain",
            return_value=mock_final_response_chain,
        ):
            result = supervisor_agent._generate_final_response(state)

        assert result == expected_output
        mock_final_response_chain.invoke.assert_called_once_with(
            {"messages": conversation_messages}
        )

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
                            description="Explain K8s deployment", assigned_to=K8S_AGENT
                        ),
                    ],
                    "messages": [
                        AIMessage(
                            content='{"subtasks": '
                            '[{"description": "Explain Kyma function deployment", "assigned_to": "KymaAgent"},'
                            '{"description": "Explain K8s deployment", "assigned_to": "KubernetesAgent"}]}',
                            name=PLANNER,
                        )
                    ],
                    "error": None,
                    "next": ROUTER,
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
                            content='{"subtasks": '
                            '[{"description": "Explain Kubernetes pod concept", '
                            '"assigned_to": "KubernetesAgent"}]}',
                            name=PLANNER,
                        )
                    ],
                    "error": None,
                    "next": ROUTER,
                },
                None,
            ),
            (
                "Exits with error if no subtasks are returned",
                "What is a Kubernetes pod?",
                '{"subtasks": []}',
                {
                    "messages": [
                        AIMessage(
                            content="Sorry, I encountered an error while processing the request. "
                            "Error: No subtasks are created for the given query: What is a Kubernetes pod?",
                            name=PLANNER,
                        )
                    ]
                },
                None,
            ),
            (
                "Exits immediately by answering for the general query",
                "Write a hello world python code?",
                '{"response": "Here is the hellow world python code: print(\'Hello, World!\')"}',
                {
                    "error": None,
                    "messages": [
                        AIMessage(
                            content="Here is the hellow world python code: print('Hello, World!')",
                            name=PLANNER,
                        )
                    ],
                    "next": END,
                    "subtasks": None,
                },
                None,
            ),
            (
                "Exits immediately for the general query even if llm doesn't return response attribute",
                "Write a hello world python code?",
                "Here is the hellow world python code: print('Hello, World!')",
                {
                    "error": None,
                    "messages": [
                        AIMessage(
                            content="Here is the hellow world python code: print('Hello, World!')",
                            name=PLANNER,
                        )
                    ],
                    "next": END,
                    "subtasks": None,
                },
                None,
            ),
            (
                "Exits of error occurs in planning",
                "What is a Kubernetes service?",
                '{"subtasks": [{"description": "Explain Kubernetes service", "assigned_to": "KubernetesAgent"}]}',
                {
                    "messages": [
                        AIMessage(
                            content="Sorry, I encountered an error while processing the request. "
                            "Error: fake error",
                            name=PLANNER,
                        )
                    ]
                },
                "fake error",
            ),
        ],
    )
    def test_agent_plan(
        self,
        supervisor_agent,
        description,
        input_query,
        plan_content,
        expected_output,
        expected_error,
    ):
        if expected_error:
            supervisor_agent._planner_chain.invoke.side_effect = Exception(
                expected_error
            )
        else:
            supervisor_agent._planner_chain.invoke.return_value.content = plan_content

        state = SupervisorState(messages=[HumanMessage(content=input_query)])
        result = supervisor_agent._plan(state)

        assert result == expected_output
