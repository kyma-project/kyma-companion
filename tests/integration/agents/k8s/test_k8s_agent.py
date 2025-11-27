from unittest.mock import Mock

import pytest
from deepeval import assert_test
from deepeval.metrics import (
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from ragas.dataset_schema import MultiTurnSample
from ragas.integrations.langgraph import convert_to_ragas_messages
from ragas.messages import ToolCall
from ragas.metrics._string import NonLLMStringSimilarity
from ragas.metrics._tool_call_accuracy import ToolCallAccuracy

from agents.common.state import SubTask
from agents.k8s.agent import KubernetesAgent
from agents.k8s.state import KubernetesAgentState
from services.k8s import IK8sClient
from utils.settings import DEEPEVAL_TESTCASE_VERBOSE, MAIN_MODEL_NAME

AGENT_STEPS_NUMBER = 25
TOOL_ACCURACY_THRESHOLD = 0.5  # Minimum acceptable tool call accuracy (50%)


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
def tool_accuracy_scorer():
    """
    Tool call accuracy metric using ragas ToolCallAccuracy.
    Uses NonLLMStringSimilarity for deterministic argument comparison.
    Threshold: 0.5 (50% accuracy required for tool selection).
    """
    metric = ToolCallAccuracy()
    metric.arg_comparison_metric = NonLLMStringSimilarity()
    return metric


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
    "test_name,state,expected_tool_calls",
    [
        # - Verifies agent makes correct k8s_query_tool call for ImagePullBackOff investigation
        (
            "Should call k8s_query_tool for ImagePullBackOff investigation",
            KubernetesAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': '', 'resource_namespace': ''}"
                    ),
                    HumanMessage(
                        content="What is causing the ImagePullBackOff status for many pods?"
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is causing the ImagePullBackOff status for many pods?",
                        "task_title": "Checking ImagePullBackOff status?",
                        "assigned_to": "KubernetesAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is causing the ImagePullBackOff status for many pods?",
                    task_title="Checking ImagePullBackOff status?",
                    assigned_to="KubernetesAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for deployments query
        (
            "Should call k8s_query_tool for deployments in namespace",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for namespace issues
        (
            "Should call k8s_query_tool for namespace issues",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for checking resources in namespace
        (
            "Should call k8s_query_tool for checking resources in namespace",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for specific deployment details
        (
            "Should call k8s_query_tool for specific deployment details",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for resource details without specific name
        (
            "Should call k8s_query_tool for resource details",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for pod crash investigation
        (
            "Should call k8s_query_tool for CrashLoopBackOff investigation",
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
            [ToolCall(name="k8s_query_tool", args={})],  # Might also call fetch_pod_logs_tool
        ),
        # Test case for node issues
        (
            "Should call k8s_query_tool for node disk pressure check",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for cluster overview
        (
            "Should call k8s_query_tool for cluster overview",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for checking all cluster resources
        (
            "Should call k8s_query_tool for all cluster resources",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for namespace overview
        (
            "Should call k8s_query_tool for namespace overview",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
        # Test case for checking all namespace resources
        (
            "Should call k8s_query_tool for all namespace resources",
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
            [ToolCall(name="k8s_query_tool", args={})],
        ),
    ],
)
@pytest.mark.asyncio
async def test_tool_calls(
    k8s_agent,
    tool_accuracy_scorer,
    test_name,
    state,
    expected_tool_calls,
):
    """
    Tests that the KubernetesAgent calls the correct tools using ragas ToolCallAccuracy.

    This test uses ragas ToolCallAccuracy metric instead of simple assertion because:
    1. It provides semantic comparison of tool calls (handles variations in tool usage)
    2. Uses NonLLMStringSimilarity for deterministic argument comparison
    3. Allows for additional tool calls beyond the expected ones
    4. Provides a score (0-1) indicating confidence in tool selection

    Threshold: 0.5 (50% accuracy) allows for some flexibility in tool call sequences.
    """
    # Phase 1: Structural assertions (fast failure if basic expectations not met)
    response = await k8s_agent._invoke_chain(state, {})
    assert isinstance(response, AIMessage), f"{test_name}: Response is not an AIMessage"
    assert response.tool_calls is not None, f"{test_name}: Expected tool calls but found none"
    assert len(response.tool_calls) > 0, f"{test_name}: Expected at least one tool call"

    # Phase 2: Semantic evaluation using ragas (only if Phase 1 passed)
    agent_messages = convert_to_ragas_messages([response])
    test_case_sample = MultiTurnSample(
        user_input=agent_messages,
        reference_tool_calls=expected_tool_calls,
    )

    score = await tool_accuracy_scorer.multi_turn_ascore(test_case_sample)
    assert score > TOOL_ACCURACY_THRESHOLD, (
        f"{test_name}: Tool call accuracy ({score:.2f}) is below the threshold of {TOOL_ACCURACY_THRESHOLD}"
    )
