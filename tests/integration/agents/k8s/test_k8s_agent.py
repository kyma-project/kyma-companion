from unittest.mock import Mock

import pytest
from deepeval import assert_test
from deepeval.metrics import (
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.common.state import SubTask
from agents.k8s.agent import KubernetesAgent
from agents.k8s.state import KubernetesAgentState
from integration.test_utils import BaseTestCase
from services.k8s import IK8sClient
from utils.settings import DEEPEVAL_TESTCASE_VERBOSE, MAIN_MODEL_NAME

AGENT_STEPS_NUMBER = 25


@pytest.fixture
def correctness_metric(evaluator_model):
    return GEval(
        name="Correctness",
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        evaluation_steps=[
            "Evaluate whether two answers are semantically similar or convey the same meaning."
            "Check whether the facts in 'actual output' contradict any facts in 'expected output'",
            "Lightly penalize omissions of detail, focusing on the main idea",
            "Vague language are permissible",
        ],
        model=evaluator_model,
        threshold=0.7,
    )


@pytest.fixture
def faithfulness_metric(evaluator_model):
    return FaithfulnessMetric(
        threshold=0.7,
        model=evaluator_model,
        include_reason=True,
        verbose_mode=DEEPEVAL_TESTCASE_VERBOSE,
    )


@pytest.fixture
def mock_k8s_client():
    return Mock(spec_set=IK8sClient)


@pytest.fixture
def k8s_agent(app_models):
    return KubernetesAgent(app_models.get(MAIN_MODEL_NAME))


class InvokeChainTestCase(BaseTestCase):
    def __init__(
        self,
        name: str,
        state: KubernetesAgentState,
        retrieval_context: str,
        expected_result: str,
        expected_tool_call: str,
        should_raise: bool,
    ):
        super().__init__(name)
        self.state = state
        self.retrieval_context = retrieval_context
        self.expected_result = expected_result
        self.expected_tool_call = expected_tool_call
        self.should_raise = should_raise


def create_invoke_chain_test_cases():
    return [
        InvokeChainTestCase(
            "Should mention Joule context when pod details are missing",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster' }"),
                    HumanMessage(content="Why is my pod in error state?"),
                ],
                subtasks=[
                    {
                        "description": "Why is my pod in error state?",
                        "task_title": "Why is my pod in error state?",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="Why is my pod in error state?",
                    task_title="Why is my pod in error state?",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "To determine why your pod is in an error state, I need to know the specific pod name and its namespace. Joule enhances your workflow by using the active resource in your Kyma dashboard as the context for your queries. "
            "This ensures that when you ask questions, Joule delivers relevant and tailored answers specific to the resource you're engaged with, making your interactions both efficient and intuitive.",
            None,
            False,
        ),
    ]


@pytest.mark.parametrize("test_case", create_invoke_chain_test_cases())
@pytest.mark.asyncio
async def test_invoke_chain(
    k8s_agent,
    correctness_metric,
    faithfulness_metric,
    test_case: InvokeChainTestCase,
):
    """Tests the K8S agent's invoke_chain method"""
    # When: We invoke the agent chain
    result = await k8s_agent.agent_chain.ainvoke(test_case.state)

    if test_case.should_raise:
        pytest.fail(f"{test_case.name}: Expected an exception to be raised")

    if test_case.expected_result:
        # Extract the last message content
        agent_response = result["agent_messages"][-1].content

        # Then: We evaluate the response using correctness and faithfulness
        llm_test_case = LLMTestCase(
            input=str(test_case.state.messages[-1].content),
            actual_output=agent_response,
            expected_output=test_case.expected_result,
            retrieval_context=(
                [test_case.retrieval_context] if test_case.retrieval_context else []
            ),
        )
        assert_test(
            llm_test_case,
            [correctness_metric, faithfulness_metric],
            f"{test_case.name}: Response should be correct and faithful",
        )


class ToolCallTestCase(BaseTestCase):
    def __init__(
        self,
        name: str,
        state: KubernetesAgentState,
        expected_tool_call: str,
    ):
        super().__init__(name)
        self.state = state
        self.expected_tool_call = expected_tool_call


def create_tool_call_test_cases():
    return [
        ToolCallTestCase(
            "Should call k8s_query_tool for ImagePullBackOff investigation",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': '', 'resource_namespace': ''}"
                    ),
                    HumanMessage(
                        content="What is causing the CrashLoopBackOff status for many pods in default namespace?"
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is causing the CrashLoopBackOff status for many pods in default namespace?",
                        "task_title": "Checking CrashLoopBackOff status?",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is causing the CrashLoopBackOff status for many pods in default namespace?",
                    task_title="Checking CrashLoopBackOff status?",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for deployments in specific namespace",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'v1', 'resource_namespace': 'default', 'resource_kind': 'Pod'}"
                    ),
                    HumanMessage(
                        content="What deployments exist in the 'kube-system' namespace?"
                    ),
                ],
                subtasks=[
                    {
                        "description": "What deployments exist in the 'kube-system' namespace?",
                        "task_title": "Check existing deployment",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="What deployments exist in the 'kube-system' namespace?",
                    task_title="Check existing deployment",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for namespace issue detection",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_namespace': 'production'}"),
                    HumanMessage(content="Is there any issue with my namespace"),
                ],
                subtasks=[
                    {
                        "description": "Is there any issue with my namespace",
                        "task_title": "Namespace overview",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="Is there any issue with my namespace",
                    task_title="Namespace overview",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for checking namespace resources",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_namespace': 'production'}"),
                    HumanMessage(content="Check resources in the namespace"),
                ],
                subtasks=[
                    {
                        "description": "Check resources in the namespace",
                        "task_title": "check resources",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="Check resources in the namespace",
                    task_title="check resources",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for specific deployment details by name",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'apps/v1', 'resource_namespace': 'default', 'resource_kind': 'Deployment'}"
                    ),
                    HumanMessage(content="Show me the details of my-app deployment"),
                ],
                subtasks=[
                    {
                        "description": "Show me the details of my-app deployment",
                        "task_title": "Deployment details",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="Show me the details of my-app deployment",
                    task_title="Deployment details",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for resource details using context",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'apps/v1', 'resource_namespace': 'default', 'resource_kind': 'Deployment'}"
                    ),
                    HumanMessage(content="Show me the details of resource"),
                ],
                subtasks=[
                    {
                        "description": "Show me the details of resource",
                        "task_title": "Deployment details",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="Show me the details of resource",
                    task_title="Deployment details",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for pod CrashLoopBackOff investigation",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'v1', 'resource_namespace': 'monitoring', 'resource_kind': 'Pod'}"
                    ),
                    HumanMessage(
                        content="Why is my prometheus pod in CrashLoopBackOff?"
                    ),
                ],
                subtasks=[
                    {
                        "description": "Why is my prometheus pod in CrashLoopBackOff?",
                        "task_title": "Pod status investigation",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="Why is my prometheus pod in CrashLoopBackOff?",
                    task_title="Pod status investigation",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for cluster-wide node disk pressure check",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': '', 'resource_namespace': ''}"
                    ),
                    HumanMessage(content="Are there any nodes with disk pressure?"),
                ],
                subtasks=[
                    {
                        "description": "Are there any nodes with disk pressure?",
                        "task_title": "Cluster health check",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="Are there any nodes with disk pressure?",
                    task_title="Cluster health check",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for cluster overview request",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'apps/v1', 'resource_namespace': 'default', 'resource_kind': 'Deployment'}"
                    ),
                    HumanMessage(content="give me cluster overview"),
                ],
                subtasks=[
                    {
                        "description": "give me cluster overview",
                        "task_title": "Cluster overview",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="give me cluster overview",
                    task_title="Cluster overview",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool when checking all cluster resources",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'apps/v1', 'resource_namespace': 'default', 'resource_kind': 'Deployment'}"
                    ),
                    HumanMessage(content="check all resources in cluster"),
                ],
                subtasks=[
                    {
                        "description": "check all resources in cluster",
                        "task_title": "Cluster overview",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="check all resources in cluster",
                    task_title="Cluster overview",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool for namespace overview request",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'apps/v1', 'resource_namespace': 'default', 'resource_kind': 'Deployment'}"
                    ),
                    HumanMessage(content="give me namespace overview"),
                ],
                subtasks=[
                    {
                        "description": "give me namespace overview",
                        "task_title": "Namespace overview",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="give me namespace overview",
                    task_title="Namespace overview",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        ToolCallTestCase(
            "Should call k8s_query_tool when checking all namespace resources",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'apps/v1', 'resource_namespace': 'default', 'resource_kind': 'Deployment'}"
                    ),
                    HumanMessage(content="check all resources in namespace"),
                ],
                subtasks=[
                    {
                        "description": "check all resources in namespace",
                        "task_title": "Namespace overview",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="check all resources in namespace",
                    task_title="Namespace overview",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
    ]


@pytest.mark.parametrize("test_case", create_tool_call_test_cases())
@pytest.mark.asyncio
async def test_tool_calls(k8s_agent, test_case: ToolCallTestCase):
    """Tests that the K8S agent makes correct tool calls"""
    # When: We invoke the agent chain
    result = await k8s_agent.agent_chain.ainvoke(test_case.state)

    # Then: Verify the agent called the expected tool
    agent_last_message = result["agent_messages"][-1]

    assert isinstance(
        agent_last_message, AIMessage
    ), f"{test_case.name}: Expected AIMessage"
    assert (
        agent_last_message.tool_calls
    ), f"{test_case.name}: Expected tool calls in response"
    assert (
        agent_last_message.tool_calls[0]["name"] == test_case.expected_tool_call
    ), f"{test_case.name}: Expected tool call to {test_case.expected_tool_call}"
