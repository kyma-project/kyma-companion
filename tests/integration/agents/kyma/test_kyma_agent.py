from unittest.mock import Mock

import pytest
from deepeval import assert_test
from deepeval.metrics import (
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
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
from integration.test_utils import BaseTestCase
from services.k8s import IK8sClient
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
def kyma_agent(app_models):
    return KymaAgent(app_models)


class InvokeChainTestCase(BaseTestCase):
    def __init__(
        self,
        name: str,
        state: KymaAgentState,
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
            "Should mention Joule context when Function details are missing",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2'}"
                    ),
                    HumanMessage(
                        content="Why is the pod of the serverless Function not ready?"
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/functions"
                                },
                            },
                        ],
                    ),
                    ToolMessage(
                        content="Please specify the function name.",
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "Why is the pod of the serverless Function not ready?",
                        "task_title": "Why is the pod of the serverless Function not ready?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="Why is the pod of the serverless Function not ready?",
                    task_title="Why is the pod of the serverless Function not ready?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "I need more information to answer this question. Please provide the name and namespace of the Function whose pod is not ready. This will help me investigate the specific issue and provide a solution tailored to your resource. ",
            None,
            False,
        ),
        InvokeChainTestCase(
            "Should diagnose API Rule with wrong access strategy",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/kyma-app-apirule-broken/apirules"
                                },
                            },
                        ],
                    ),
                    ToolMessage(
                        content=API_RULE_WITH_WRONG_ACCESS_STRATEGY,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "API Rule validation error"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content=KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with api rule?",
                        "task_title": "API Rule issue",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with api rule?",
                    task_title="API Rule issue",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            EXPECTED_API_RULE_RESPONSE,
            EXPECTED_API_RULE_RESPONSE,
            None,
            False,
        ),
        InvokeChainTestCase(
            "Should call kyma_query_tool for initial API Rule query",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with api rule?",
                        "task_title": "API Rule issue",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with api rule?",
                    task_title="API Rule issue",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            None,
            "kyma_query_tool",
            False,
        ),
        InvokeChainTestCase(
            "Should call search_kyma_doc after getting API Rule resource",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/kyma-app-apirule-broken/apirules"
                                },
                            },
                        ],
                    ),
                    ToolMessage(
                        content=EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with api rule?",
                        "task_title": "API Rule issue",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with api rule?",
                    task_title="API Rule issue",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            None,
            "search_kyma_doc",
            False,
        ),
        InvokeChainTestCase(
            "Should diagnose Serverless Function with JavaScript syntax error",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'function-syntax-error', 'resource_namespace': 'default'}"
                    ),
                    HumanMessage(content="Why is my function not working?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions/function-syntax-error"
                                },
                            },
                        ],
                    ),
                    ToolMessage(
                        content=SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {
                                    "query": "Serverless function pod not ready troubleshooting"
                                },
                            },
                        ],
                    ),
                    ToolMessage(
                        content=KYMADOC_FUNCTION_TROUBLESHOOTING,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[
                    {
                        "description": "Why is my function not working?",
                        "task_title": "Function issue",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="Why is my function not working?",
                    task_title="Function issue",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            KYMADOC_FOR_SERVERLESS_FUNCTION_POD_NOT_READY,
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE,
            None,
            False,
        ),
        InvokeChainTestCase(
            "Should diagnose Serverless Function with no replicas configured",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'function-no-replicas', 'resource_namespace': 'default'}"
                    ),
                    HumanMessage(content="Why is my function not scaling?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions/function-no-replicas"
                                },
                            },
                        ],
                    ),
                    ToolMessage(
                        content=FUNCTION_NO_REPLICAS,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "Why is my function not scaling?",
                        "task_title": "Function scaling issue",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="Why is my function not scaling?",
                    task_title="Function scaling issue",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE_NO_REPLICAS,
            None,
            False,
        ),
        InvokeChainTestCase(
            "Should answer general Kyma question using only search_kyma_doc",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'BtpOperator', 'resource_api_version': 'operator.kyma-project.io/v1alpha1'}"
                    ),
                    HumanMessage(content="How to configure BTP Manager?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "BTP Manager configuration"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content=RETRIEVAL_CONTEXT,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "How to configure BTP Manager?",
                        "task_title": "BTP Manager configuration",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="How to configure BTP Manager?",
                    task_title="BTP Manager configuration",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            RETRIEVAL_CONTEXT,
            EXPECTED_BTP_MANAGER_RESPONSE,
            None,
            False,
        ),
        InvokeChainTestCase(
            "Should search Kyma docs once when no relevant documentation found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster'}"),
                    HumanMessage(content="How do I configure custom metrics in Kyma?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "custom metrics configuration"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content="No relevant documentation found.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "How do I configure custom metrics in Kyma?",
                        "task_title": "Custom metrics config",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="How do I configure custom metrics in Kyma?",
                    task_title="Custom metrics config",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "I apologize, but I couldn't find specific documentation about configuring custom metrics in Kyma. "
            "This feature might not be covered in the current documentation, or it might be handled differently. "
            "I recommend checking the official Kyma documentation or reaching out to the Kyma community for guidance.",
            None,
            False,
        ),
        InvokeChainTestCase(
            "Should search Kyma docs for serverless deployment when no docs found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster'}"),
                    HumanMessage(
                        content="How to deploy serverless functions with custom domains?"
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {
                                    "query": "serverless functions custom domains"
                                },
                            },
                        ],
                    ),
                    ToolMessage(
                        content="No relevant documentation found.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "How to deploy serverless functions with custom domains?",
                        "task_title": "Serverless custom domains",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="How to deploy serverless functions with custom domains?",
                    task_title="Serverless custom domains",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "I apologize, but I couldn't find specific documentation about deploying serverless functions with custom domains in Kyma. "
            "This might require additional configuration through API Rules or Istio VirtualServices. "
            "For detailed configuration examples, please check the Kyma API Gateway documentation.",
            None,
            False,
        ),
        InvokeChainTestCase(
            "Should search Kyma docs for API Gateway rate limiting when no docs found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster'}"),
                    HumanMessage(
                        content="How to configure rate limiting in API Gateway?"
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "API Gateway rate limiting"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content="No relevant documentation found.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "How to configure rate limiting in API Gateway?",
                        "task_title": "API Gateway rate limiting",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="How to configure rate limiting in API Gateway?",
                    task_title="API Gateway rate limiting",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "I apologize, but I couldn't find specific documentation about configuring rate limiting in Kyma's API Gateway. "
            "Rate limiting in Kyma might be configured through Istio's traffic management features or custom Envoy filters. "
            "For detailed configuration examples, please check the Kyma API Gateway documentation "
            "or Istio's traffic management guides.",
            None,
            False,
        ),
    ]


@pytest.mark.parametrize("test_case", create_invoke_chain_test_cases())
@pytest.mark.asyncio
async def test_invoke_chain(
    kyma_agent,
    correctness_metric,
    faithfulness_metric,
    test_case: InvokeChainTestCase,
):
    """Tests the Kyma agent's invoke_chain method"""
    # Given: A KymaAgent instance and test parameters

    if test_case.should_raise:
        # When: the chain is invoked and an error is expected
        # Then: the expected error should be raised
        with pytest.raises(test_case.expected_result):
            kyma_agent._invoke_chain(test_case.state, {})
    else:
        # When: the chain is invoked normally
        response = await kyma_agent._invoke_chain(test_case.state, {})
        assert isinstance(response, AIMessage), f"{test_case.name}: Expected AIMessage"

        # Then: Verify the response based on expected behavior
        if test_case.expected_tool_call:
            # for tool call cases, verify tool call properties
            assert (
                response.tool_calls is not None
            ), f"{test_case.name}: Expected tool calls but found none"
            assert (
                len(response.tool_calls) > 0
            ), f"{test_case.name}: Expected at least one tool call"
            tool_call = response.tool_calls[0]
            assert tool_call.get("type") == "tool_call"
            assert (
                tool_call.get("name") == test_case.expected_tool_call
            ), f"{test_case.name}: Expected {test_case.expected_tool_call}"
        else:
            # for content response cases, verify using deepeval metrics
            llm_test_case = LLMTestCase(
                input=test_case.state.my_task.description,
                actual_output=response.content,
                expected_output=(
                    test_case.expected_result if test_case.expected_result else None
                ),
                retrieval_context=(
                    [test_case.retrieval_context] if test_case.retrieval_context else []
                ),
            )
            assert_test(
                llm_test_case,
                [correctness_metric, faithfulness_metric],
                f"{test_case.name}: Response should be correct and faithful",
            )


class ToolCallingTestCase(BaseTestCase):
    def __init__(
        self,
        name: str,
        state: KymaAgentState,
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


def create_tool_calling_test_cases():
    return [
        ToolCallingTestCase(
            "Should not retry tool calling after multiple failures",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster'}"),
                    HumanMessage(content="What Kyma modules are available?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "Kyma modules"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content="Error: Failed to retrieve documentation.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "available Kyma modules"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content="Error: Failed to retrieve documentation.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What Kyma modules are available?",
                        "task_title": "Kyma modules",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What Kyma modules are available?",
                    task_title="Kyma modules",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "I apologize, but I'm having trouble retrieving the documentation about Kyma modules at the moment. "
            "Please try again later or check the official Kyma documentation directly.",
            None,
            False,
        ),
        ToolCallingTestCase(
            "Should retry tool calling after first failure",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster'}"),
                    HumanMessage(content="What is Kyma eventing?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "Kyma eventing"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content="Error: Timeout.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is Kyma eventing?",
                        "task_title": "Kyma eventing",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is Kyma eventing?",
                    task_title="Kyma eventing",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            None,
            "search_kyma_doc",
            False,
        ),
        ToolCallingTestCase(
            "Should use search_kyma_doc for Kyma-specific question (1)",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster'}"),
                    HumanMessage(content="How does Kyma service mesh work?"),
                ],
                subtasks=[
                    {
                        "description": "How does Kyma service mesh work?",
                        "task_title": "Kyma service mesh",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="How does Kyma service mesh work?",
                    task_title="Kyma service mesh",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            None,
            "search_kyma_doc",
            False,
        ),
        ToolCallingTestCase(
            "Should use search_kyma_doc for Kyma-specific question (2)",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster'}"),
                    HumanMessage(content="What is Kyma telemetry?"),
                ],
                subtasks=[
                    {
                        "description": "What is Kyma telemetry?",
                        "task_title": "Kyma telemetry",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is Kyma telemetry?",
                    task_title="Kyma telemetry",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            None,
            "search_kyma_doc",
            False,
        ),
        ToolCallingTestCase(
            "Should use search_kyma_doc for Kyma-specific question (3)",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_kind': 'Cluster'}"),
                    HumanMessage(
                        content="How to configure Kyma application connector?"
                    ),
                ],
                subtasks=[
                    {
                        "description": "How to configure Kyma application connector?",
                        "task_title": "Application connector config",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="How to configure Kyma application connector?",
                    task_title="Application connector config",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            None,
            "search_kyma_doc",
            False,
        ),
    ]


@pytest.mark.parametrize("test_case", create_tool_calling_test_cases())
@pytest.mark.asyncio
async def test_tool_calling(
    kyma_agent,
    correctness_metric,
    faithfulness_metric,
    test_case: ToolCallingTestCase,
):
    """Tests that the Kyma agent makes correct tool calls"""
    # Given: A KymaAgent instance and test parameters

    if test_case.should_raise:
        # When: the chain is invoked and an error is expected
        with pytest.raises(test_case.expected_result):
            kyma_agent._invoke_chain(test_case.state, {})
    else:
        # When: the chain is invoked normally
        response = await kyma_agent._invoke_chain(test_case.state, {})
        assert isinstance(response, AIMessage), f"{test_case.name}: Expected AIMessage"

        # Then: Verify the response based on expected behavior
        if test_case.expected_tool_call:
            # Verify tool call properties
            assert (
                response.tool_calls is not None
            ), f"{test_case.name}: Expected tool calls but found none"
            assert (
                len(response.tool_calls) > 0
            ), f"{test_case.name}: Expected at least one tool call"
            tool_call = response.tool_calls[0]
            assert tool_call.get("type") == "tool_call"
            assert (
                tool_call.get("name") == test_case.expected_tool_call
            ), f"{test_case.name}: Expected {test_case.expected_tool_call}"
        else:
            # Verify content response
            llm_test_case = LLMTestCase(
                input=test_case.state.my_task.description,
                actual_output=response.content,
                expected_output=(
                    test_case.expected_result if test_case.expected_result else None
                ),
                retrieval_context=(
                    [test_case.retrieval_context] if test_case.retrieval_context else []
                ),
            )
            assert_test(
                llm_test_case,
                [correctness_metric, faithfulness_metric],
                f"{test_case.name}: Response should be correct and faithful",
            )
