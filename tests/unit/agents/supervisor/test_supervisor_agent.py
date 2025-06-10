from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.constants import END

from agents.common.constants import COMMON, ERROR, PLANNER
from agents.common.state import CompanionState, Plan, SubTask
from agents.k8s.agent import K8S_AGENT
from agents.kyma.agent import KYMA_AGENT
from agents.supervisor.agent import FINALIZER, ROUTER, SupervisorAgent
from agents.supervisor.state import SupervisorState
from utils.models.factory import IModel
from utils.settings import (
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
    MAIN_MODEL_NAME,
)


@pytest.fixture
def mock_models():
    return {
        MAIN_MODEL_MINI_NAME: MagicMock(spec=IModel),
        MAIN_MODEL_NAME: MagicMock(spec=IModel),
        MAIN_EMBEDDING_MODEL_NAME: MagicMock(spec=Embeddings),
    }


class TestSupervisorAgent:
    @pytest.fixture
    def supervisor_agent(self, mock_models):
        agent = SupervisorAgent(
            models=mock_models, members=[K8S_AGENT, KYMA_AGENT, COMMON, FINALIZER]
        )
        return agent

    @pytest.mark.parametrize(
        "subtasks, messages, expected_next, expected_subtasks, expected_error",
        [
            (
                [
                    SubTask(
                        description="Task 1",
                        task_title="Task 1",
                        assigned_to=K8S_AGENT,
                        status="pending",
                    ),
                    SubTask(
                        description="Task 2",
                        task_title="Task 2",
                        assigned_to=KYMA_AGENT,
                        status="pending",
                    ),
                ],
                [
                    HumanMessage(content="Test message 1"),
                    AIMessage(content="Test message 2"),
                ],
                K8S_AGENT,
                [
                    SubTask(
                        description="Task 1",
                        task_title="Task 1",
                        assigned_to=K8S_AGENT,
                        status="pending",
                    ),
                    SubTask(
                        description="Task 2",
                        task_title="Task 2",
                        assigned_to=KYMA_AGENT,
                        status="pending",
                    ),
                ],
                None,
            ),
            (
                [
                    SubTask(
                        description="Task 2",
                        task_title="Task 2",
                        assigned_to=KYMA_AGENT,
                        status="pending",
                    )
                ],
                [AIMessage(content="Fake message")],
                KYMA_AGENT,
                [
                    SubTask(
                        description="Task 2",
                        task_title="Task 2",
                        assigned_to=KYMA_AGENT,
                        status="pending",
                    )
                ],
                None,
            ),
            (
                [
                    SubTask(
                        description="Task 3",
                        task_title="Task 3",
                        assigned_to=K8S_AGENT,
                        status="completed",
                    )
                ],
                [],
                FINALIZER,
                [
                    SubTask(
                        description="Task 3",
                        task_title="Task 3",
                        assigned_to=K8S_AGENT,
                        status="completed",
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
            assert result["subtasks"] == expected_subtasks
            assert "error" not in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "description, input_query, conversation_messages, subtasks, final_response_content, expected_output, expected_error",
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
                [
                    SubTask(
                        description="Explain Kyma function deployment",
                        task_title="Explain Kyma function deployment",
                        assigned_to=KYMA_AGENT,
                        status="completed",
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
                [
                    SubTask(
                        description="Explain Kubernetes",
                        task_title="Explain Kubernetes",
                        assigned_to=K8S_AGENT,
                        status="completed",
                    ),
                ],
                "",
                {
                    "messages": [AIMessage(content="", name="Finalizer")],
                    "next": "__end__",
                },
                "",
            ),
            (
                "Do not generate final response as all subtasks failed",
                "What is Kubernetes? and what is KYMA",
                [
                    HumanMessage(content="What is Kubernetes?"),
                    AIMessage(
                        content="Kubernetes is a container orchestration platform.",
                        name="KubernetesAgent",
                    ),
                ],
                [
                    SubTask(
                        description="Explain Kubernetes",
                        task_title="Explain Kubernetes",
                        assigned_to=K8S_AGENT,
                        status="error",
                    ),
                    SubTask(
                        description="Explain Kyma",
                        task_title="Explain Kyma",
                        assigned_to=KYMA_AGENT,
                        status="error",
                    ),
                ],
                None,  # this content should be handled by finalizer itself
                {
                    "messages": [
                        AIMessage(
                            content="We're unable to provide a response at this time due to agent failure. "
                            "Please try again or reach out to our support team for further assistance.",
                            name="Finalizer",
                        )
                    ],
                    "next": "__end__",
                },
                None,
            ),
        ],
    )
    async def test_agent_generate_final_response(
        self,
        supervisor_agent,
        description,
        input_query,
        conversation_messages,
        subtasks,
        final_response_content,
        expected_output,
        expected_error,
    ):
        # Given
        state = SupervisorState(messages=conversation_messages, subtasks=subtasks)

        mock_final_response_chain = AsyncMock()
        if final_response_content is not None:
            mock_final_response_chain.ainvoke.return_value.content = (
                final_response_content
            )

        with patch.object(
            supervisor_agent,
            "_final_response_chain",
            return_value=mock_final_response_chain,
        ):
            # When
            result = await supervisor_agent._generate_final_response(state)

            # Then
            assert result == expected_output

            if final_response_content is not None:
                mock_final_response_chain.ainvoke.assert_called_once_with(
                    config=None, input={"messages": conversation_messages}
                )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case, input_query, mock_plan_content, expected_output, expected_error",
        [
            (
                "Plans multiple subtasks successfully",
                "How do I deploy a Kyma function?",
                '{ "subtasks": [{"description": "Explain Kyma function deployment", "task_title": "Explain Kyma function deployment", "assigned_to": "KymaAgent" ,"status" : "pending"},'
                '{"description": "Explain K8s deployment", "task_title": "Explain K8s deployment", "assigned_to": "KubernetesAgent","status" : "pending"}]}',
                {
                    "subtasks": [
                        SubTask(
                            description="Explain Kyma function deployment",
                            task_title="Explain Kyma function deployment",
                            assigned_to=KYMA_AGENT,
                        ),
                        SubTask(
                            description="Explain K8s deployment",
                            task_title="Explain K8s deployment",
                            assigned_to=K8S_AGENT,
                        ),
                    ],
                    "messages": [],
                    "error": None,
                    "next": ROUTER,
                },
                None,
            ),
            (
                "Plans a single subtask successfully",
                "What is a Kubernetes pod?",
                '{ "subtasks": [{"description": "Explain Kubernetes pod concept","task_title": "Explain Kubernetes pod concept", "assigned_to": "KubernetesAgent","status" : "pending"}]}',
                {
                    "subtasks": [
                        SubTask(
                            description="Explain Kubernetes pod concept",
                            task_title="Explain Kubernetes pod concept",
                            assigned_to="KubernetesAgent",
                        )
                    ],
                    "messages": [],
                    "error": None,
                    "next": ROUTER,
                },
                None,
            ),
            (
                "Exits with error if no subtasks are returned",
                "What is a Kubernetes pod?",
                '{ "subtasks": null}',
                {
                    ERROR: "Unexpected error while processing the request. Please try again later.",
                    "messages": [
                        AIMessage(
                            content="Unexpected error while processing the request. Please try again later.",
                            name=PLANNER,
                        )
                    ],
                    "next": END,
                    "subtasks": [],
                },
                None,
            ),
            (
                "Exits of error occurs in planning",
                "What is a Kubernetes service?",
                '{"subtasks": [{"description": "Explain Kubernetes service", "assigned_to": "KubernetesAgent","status" : "pending"}]}',
                {
                    ERROR: "Unexpected error while processing the request. Please try again later.",
                    "messages": [
                        AIMessage(
                            content="Unexpected error while processing the request. Please try again later.",
                            name=PLANNER,
                        )
                    ],
                    "next": END,
                    "subtasks": [],
                },
                "fake error",
            ),
        ],
    )
    async def test_agent_plan(
        self,
        supervisor_agent,
        test_case,
        input_query,
        mock_plan_content,
        expected_output,
        expected_error,
    ):
        # Mock _invoke_planner instead of _planner_chain
        with patch.object(
            supervisor_agent, "_invoke_planner", new_callable=AsyncMock
        ) as mock_invoke_planner:
            if expected_error:
                mock_invoke_planner.side_effect = Exception(expected_error)
            else:
                mock_invoke_planner.return_value = Plan.model_validate_json(
                    mock_plan_content
                )

            state = SupervisorState(messages=[HumanMessage(content=input_query)])
            result = await supervisor_agent._plan(state)

            assert result == expected_output, test_case
            mock_invoke_planner.assert_called_once_with(state)
