from unittest.mock import Mock

import pytest
from deepeval import evaluate
from deepeval.metrics import (
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.common.state import SubTask
from agents.k8s.agent import KubernetesAgent
from agents.k8s.state import KubernetesAgentState
from agents.kyma.state import KymaAgentState
from integration.agents.fixtures.api_rule import (
    API_RULE_WITH_WRONG_ACCESS_STRATEGY,
    EXPECTED_API_RULE_RESPONSE,
    EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
    KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
)
from integration.agents.fixtures.btp_manager import (
    EXPECTED_BTP_MANAGER_RESPONSE,
    RETRIEVAL_CONTEXT,
)
from integration.agents.fixtures.serverless_function import (
    EXPECTED_SERVERLESS_FUNCTION_RESPONSE,
    EXPECTED_SERVERLESS_FUNCTION_RESPONSE_NO_REPLICAS,
    FUNCTION_NO_REPLICAS,
    KYMADOC_FOR_SERVERLESS_FUNCTION_POD_NOT_READY,
    KYMADOC_FUNCTION_TROUBLESHOOTING,
    SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
)
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
    ],
)
@pytest.mark.asyncio
async def test_invoke_chain(
    k8s_agent,
    correctness_metric,
    faithfulness_metric,
    test_case,
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
