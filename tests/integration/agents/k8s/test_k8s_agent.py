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


@pytest.mark.parametrize(
    "test_case,state,retrieval_context,expected_result,expected_tool_call,should_raise",
    [
        (
            "Should mention about Joule context in kyma dashboard",
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
    ],
)
@pytest.mark.asyncio
async def test_invoke_chain(
    k8s_agent,
    correctness_metric,
    faithfulness_metric,
    test_case,
    state,
    retrieval_context,
    expected_result,
    expected_tool_call,
    should_raise,
):
    """
    Tests that the _invoke_chain method of the KubernetesAgent returns the expected response
    for the given user query, subtask and tool calls.
    """
    # Given: A KubernetesAgent instance and test parameters

    # When: the chain is invoked normally
    response = await k8s_agent._invoke_chain(state, {})
    assert isinstance(response, AIMessage), test_case

    # Then: Verify the response based on expected behavior
    if expected_tool_call:
        # for tool call cases, verify tool call properties
        assert response.tool_calls is not None, "Expected tool calls but found none"
        assert len(response.tool_calls) > 0, "Expected at least one tool call"
        tool_call = response.tool_calls[0]
        assert tool_call.get("type") == "tool_call"
        assert tool_call.get("name") == expected_tool_call
    else:
        # for content response cases, verify using deepeval metrics
        test_case = LLMTestCase(
            input=state.my_task.description,
            actual_output=response.content,
            expected_output=expected_result if expected_result else None,
            retrieval_context=([retrieval_context] if retrieval_context else []),
        )
        # evaluate if the gotten response is semantically similar and faithful to the expected response
        assert_test(test_case, [correctness_metric, faithfulness_metric]), test_case


@pytest.mark.parametrize(
    "state,expected_tool_call",
    [
        # - Verifies agent makes correct k8s_overview_query_tool call
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_api_version': '', 'resource_namespace': ''}"),
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
        # Test case for pod query
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'v1', 'resource_namespace': 'default', 'resource_kind': 'Pod'}"
                    ),
                    HumanMessage(content="What deployments exist in the 'kube-system' namespace?"),
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
        # Test case for namespace overview
        (
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
        # Test case for specific resource query with full details
        (
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
        # Test case for specific resource query with full details
        (
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
        # Test case for pod status investigation
        (
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'v1', 'resource_namespace': 'monitoring', 'resource_kind': 'Pod'}"
                    ),
                    HumanMessage(content="Why is my prometheus pod in CrashLoopBackOff?"),
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
                    SystemMessage(content="{'resource_api_version': '', 'resource_namespace': ''}"),
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
        # Test case for cluster overview query
        (
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
        (
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
        # Test case for namespace overview query
        (
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
        # Test case for namespace overview query
        (
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
    ],
)
@pytest.mark.asyncio
async def test_tool_calls(
    k8s_agent,
    faithfulness_metric,
    state,
    expected_tool_call,
):
    # Given: A KubernetesAgent instance and test parameters

    # When: the chain is invoked normally
    response = await k8s_agent._invoke_chain(state, {})
    assert isinstance(response, AIMessage)

    # for tool call cases, verify tool call properties
    if expected_tool_call:
        assert response.tool_calls is not None, "Expected tool calls but found none"
        assert len(response.tool_calls) > 0, "Expected at least one tool call"
    tool_call = response.tool_calls[0]
    assert tool_call.get("type") == "tool_call"
    assert tool_call.get("name") == expected_tool_call
