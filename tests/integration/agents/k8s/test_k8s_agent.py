from unittest.mock import Mock

import pytest
from deepeval.metrics import (
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.common.state import SubTask
from agents.k8s.agent import KubernetesAgent
from agents.k8s.state import KubernetesAgentState
from services.k8s import IK8sClient
from utils.models.factory import ModelType
from utils.settings import DEEPEVAL_TESTCASE_VERBOSE

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
    return KubernetesAgent(app_models.get(ModelType.GPT4O))


@pytest.mark.parametrize(
    "state,expected_tool_call",
    [
        # - Verifies agent makes correct k8s_query_tool call
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with ApiRule?",
                        "task_title": "What is wrong with ApiRule?",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with api rule?",
                    task_title="What is wrong with api rule?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_query_tool",
        ),
        # - Verifies agent makes correct k8s_overview_query_tool call
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': '', 'resource_namespace': ''}"
                    ),
                    HumanMessage(
                        content="What is causing the ImagePullBackOff status for multiple pods?"
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is causing the ImagePullBackOff status for multiple pods?",
                        "task_title": "Checking ImagePullBackOff status?",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is causing the ImagePullBackOff status for multiple pods?",
                    task_title="Checking ImagePullBackOff status?",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_overview_query_tool",
        ),
        # Test case for pod logs query
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'default', 'resource_kind': 'Pod'}"
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
        # Test case for namespace overview
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_namespace': 'production'}"
                    ),
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
            "k8s_overview_query_tool",
        ),
        # Test case for namespace overview
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_namespace': 'production'}"
                    ),
                    HumanMessage(content="Show me cluster-level resource usage"),
                ],
                subtasks=[
                    {
                        "description": "Show me cluster-level resource usage",
                        "task_title": "check resource usage",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="Show me cluster-level resource usage",
                    task_title="check resource usage",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "k8s_overview_query_tool",
        ),
        # Test case for specific resource query with full details
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'apps/v1', 'resource_namespace': 'default', 'resource_kind': 'Deployment'}"
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
        # Test case for pod status investigation
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'monitoring', 'resource_kind': 'Pod'}"
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
            "k8s_query_tool",  # Might first call k8s_query_tool then fetch_pod_logs_tool
        ),
        # Test case for cluster-wide issue
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': '', 'resource_namespace': ''}"
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
            "k8s_overview_query_tool",
        ),
    ],
)
@pytest.mark.asyncio
async def test_tool_calls(
    k8s_agent,
    correctness_metric,
    faithfulness_metric,
    state,
    expected_tool_call,
):
    # Given: A KubernetesAgent instance and test parameters

    # When: the chain is invoked normally
    response = await k8s_agent._invoke_chain(state, {})
    assert isinstance(response, AIMessage)

    # for tool call cases, verify tool call properties
    assert response.tool_calls is not None, "Expected tool calls but found none"
    assert len(response.tool_calls) > 0, "Expected at least one tool call"
    tool_call = response.tool_calls[0]
    assert tool_call.get("type") == "tool_call"
    assert tool_call.get("name") == expected_tool_call
