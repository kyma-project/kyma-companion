from textwrap import dedent
from unittest.mock import Mock

import pytest
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    GEval,
    HallucinationMetric,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.common.constants import PLANNER
from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from agents.supervisor.agent import SUPERVISOR
from integration.agents.fixtures.api_rule import (
    API_RULE_WITH_WRONG_ACCESS_STRATEGY,
    EXPECTED_API_RULE_RESPONSE,
    EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
    KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
)
from integration.agents.fixtures.serverless_function import (
    EXPECTED_SERVERLESS_FUNCTION_RESPONSE,
    EXPECTED_SERVERLESS_FUNCTION_RESPONSE_NO_REPLICAS,
    FUNCTION_NO_REPLICAS,
    KYMADOC_FOR_SERVERLESS_FUNCTION_POD_NOT_READY,
    SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
)
from services.k8s import IK8sClient
from utils.settings import DEEPEVAL_TESTCASE_VERBOSE


@pytest.fixture
def semantic_similarity_metric(evaluator_model):
    return GEval(
        name="Semantic Similarity",
        criteria=""
        "Evaluate whether two answers are semantically similar or convey the same meaning.",
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.8,
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
def hallucination_metric(evaluator_model):
    return HallucinationMetric(
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


@pytest.mark.parametrize(
    "test_case,state,context,retrieval_context,expected_result,expected_tool_call,should_raise",
    [
        (
            "API Rule with wrong access strategy",
            KymaAgentState(
                messages=[
                    AIMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                    AIMessage(
                        content='```json\n{ "subtasks": [ { "description": "What is wrong with ApiRule?", "assigned_to": "KymaAgent" } ] }\n```',
                        name=PLANNER,
                    ),
                    AIMessage(
                        content='{"next": "KymaAgent"}',
                        name=SUPERVISOR,
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
                            }
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
                                "name": "search_kyma_doc_tool",
                                "args": {"query": "APIRule validation errors"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content=KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
                        name="search_kyma_doc_tool",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="What is wrong with API rule?", assigned_to="KymaAgent"
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            ["Multiple access strategies are not allowed to be used together"],
            KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
            EXPECTED_API_RULE_RESPONSE,
            None,
            False,
        ),
        (
            "API Rule Kyma Resource Query Tool Call",
            KymaAgentState(
                messages=[
                    AIMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                    AIMessage(
                        content='```json\n{ "subtasks": [ { "description": "What is wrong with ApiRule?", "assigned_to": "KymaAgent" } ] }\n```',
                    ),
                    AIMessage(
                        content='{"next": "KymaAgent"}',
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="What is wrong with api rule?", assigned_to="KymaAgent"
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            None,
            None,
            EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
            "kyma_query_tool",
            False,
        ),
        (
            "API Rule Kyma Doc Search Tool Call",
            KymaAgentState(
                messages=[
                    AIMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                    AIMessage(
                        content='```json\n{ "subtasks": [ { "description": "What is wrong with ApiRule?", "assigned_to": "KymaAgent" } ] }\n```',
                    ),
                    AIMessage(
                        content='{"next": "KymaAgent"}',
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
                            }
                        ],
                    ),
                    ToolMessage(
                        content=API_RULE_WITH_WRONG_ACCESS_STRATEGY,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="What is wrong with ApiRule?", assigned_to="KymaAgent"
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            None,
            None,
            EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
            "search_kyma_doc_tool",
            False,
        ),
        (
            "Serverless Function with syntax error",
            KymaAgentState(
                messages=[
                    AIMessage(
                        content="The user query is related to: {'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'func1', 'resource_namespace': 'kyma-app-serverless-syntax-err'}"
                    ),
                    HumanMessage(content="what is wrong?"),
                    AIMessage(
                        content=dedent(
                            """```
                    {
                        "subtasks": [
                            {
                                "description": "What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?",
                                "assigned_to": "KymaAgent"
                            }
                        ]
                    }```"""
                        ),
                    ),
                    AIMessage(
                        content='{"next": "KymaAgent"}',
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content=SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    HumanMessage(
                        content="What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?"
                    ),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            [
                "There is no Dates object in JavaScript, but Date object. It can be initialized with `new Date()`."
            ],
            None,
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE,
            None,
            False,
        ),
        (
            "Serverless Function with no replicas",
            KymaAgentState(
                messages=[
                    AIMessage(
                        content="The user query is related to: {'resource_namespace': 'kyma-serverless-function-no-replicas'}"
                    ),
                    HumanMessage(
                        content="Why the pod of the serverless Function is not ready?"
                    ),
                    AIMessage(
                        content=dedent(
                            """```json
                            {
                                "subtasks": [
                                    {
                                        "description": "Why the pod of the serverless Function is not ready?",
                                        "assigned_to": "KymaAgent"
                                    }
                                ]
                            }
                            ```"""
                        ),
                        name=PLANNER,
                    ),
                    AIMessage(
                        content='{"next": "KymaAgent"}',
                        name=SUPERVISOR,
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                                },
                            },
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc_tool",
                                "args": {"query": "serverless Function pod not ready"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content=FUNCTION_NO_REPLICAS,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    ToolMessage(
                        content=KYMADOC_FOR_SERVERLESS_FUNCTION_POD_NOT_READY,
                        name="search_kyma_doc_tool",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="Why the pod of the serverless Function is not ready?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            [
                "The Serverless Function replicas must be greater than 0 to respond to requests"
            ],
            None,
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE_NO_REPLICAS,
            None,
            False,
        ),
    ],
)
def test_invoke_chain(
    kyma_agent,
    semantic_similarity_metric,
    faithfulness_metric,
    hallucination_metric,
    test_case,
    state,
    context,
    retrieval_context,
    expected_result,
    expected_tool_call,
    should_raise,
):
    """Test the _invoke_chain method with success, context, and error scenarios."""
    if should_raise:
        with pytest.raises(expected_result):
            kyma_agent._invoke_chain(state, {})
    else:
        response = kyma_agent._invoke_chain(state, {})
        assert isinstance(response, AIMessage)

        if expected_tool_call:
            # if tool calls are expected, assert the tool call content matches expected_tool_call
            assert response.tool_calls is not None, "Expected tool calls but found none"
            assert len(response.tool_calls) > 0, "Expected at least one tool call"
            tool_call = response.tool_calls[0]
            assert tool_call.get("type") == "tool_call"
            assert tool_call.get("name") == expected_tool_call
        else:
            # If tool calls are not expected, content should match expected_result
            test_case = LLMTestCase(
                input=state.my_task.description,
                actual_output=response.content,
                expected_output=expected_result if expected_result else None,
                context=context if context else None,
                retrieval_context=([retrieval_context] if retrieval_context else []),
            )

            # Run deepeval metrics
            results = evaluate(
                test_cases=[test_case],
                metrics=[
                    semantic_similarity_metric,
                    faithfulness_metric,
                    hallucination_metric,
                ],
            )

            # Assert all metrics pass
            assert all(
                result.success for result in results.test_results
            ), "Not all metrics passed"
