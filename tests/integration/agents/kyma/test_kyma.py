from textwrap import dedent
from unittest.mock import Mock

import pytest
from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from integration.agents.fixtures.api_rule import (
    API_RULE_WITH_WRONG_ACCESS_STRATEGY,
    EXPECTED_API_RULE_RESPONSE,
    EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
    KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
)
from integration.agents.fixtures.serverless_function import (
    EXPECTED_SERVERLESS_FUNCTION_RESPONSE,
    SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
)
from services.k8s import IK8sClient


@pytest.fixture
def answer_relevancy_metric(evaluator_model):
    return AnswerRelevancyMetric(
        threshold=0.7, model=evaluator_model, include_reason=True
    )


@pytest.fixture
def faithfulness_metric(evaluator_model):
    return FaithfulnessMetric(threshold=0.7, model=evaluator_model, include_reason=True)


@pytest.fixture
def mock_k8s_client():
    return Mock(spec_set=IK8sClient)


@pytest.fixture
def kyma_agent(app_models):
    return KymaAgent(app_models)


@pytest.mark.parametrize(
    "state,retrieval_context,expected_result,expected_tool_call,should_raise",
    [
        # API Rule Issues
        (
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
                    HumanMessage(content="What is wrong with API rule?"),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="Diagnose API Rule issues", assigned_to="KymaAgent"
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
            EXPECTED_API_RULE_RESPONSE,
            None,
            False,
        ),
        # API Rule Kyma Query Tool Call
        (
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
                    description="Diagnose API Rule issues", assigned_to="KymaAgent"
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            None,
            EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
            "kyma_query_tool",
            False,
        ),
        # API Rule with Kyma Doc Search Tool Call - Agent must still query doc search tool
        (
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
                    description="Diagnose API Rule issues", assigned_to="KymaAgent"
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            None,
            EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
            "search_kyma_doc_tool",
            False,
        ),
        # Serverless Function with syntax error
        (
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
            None,
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE,
            None,
            False,
        ),
    ],
)
def test_invoke_chain(
    kyma_agent,
    answer_relevancy_metric,
    faithfulness_metric,
    state,
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
                input=state.messages[-1].content,
                actual_output=response.content,
                expected_output=expected_result,
                retrieval_context=([retrieval_context] if retrieval_context else []),
            )

            # Run deepeval metrics
            results = evaluate(
                test_cases=[test_case],
                metrics=[answer_relevancy_metric, faithfulness_metric],
            )

            # Assert all metrics pass
            assert all(
                result.success for result in results.test_results
            ), "Not all metrics passed"
