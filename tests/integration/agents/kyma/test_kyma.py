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
    KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
)
from integration.agents.fixtures.serverless_function import (
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
    "state,retrieval_context,expected_result,should_raise",
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
                    HumanMessage(content="What is wrong with ApiRule?"),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="Diagnose API Rule issues", assigned_to="KymaAgent"
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
            dedent(
                """
            Looking at the APIRule configuration and the error message, there is a specific issue with the access strategies configuration. The error occurs because you're trying to use multiple access strategies (`no_auth` and `allow`) together, which is not allowed.
        
            The error message clearly states two validation errors:
            1. `allow` access strategy cannot be combined with other access strategies
            2. `no_auth` access strategy cannot be combined with other access strategies
            
            Here's what's wrong in the current configuration:
            ```yaml
            accessStrategies:
            - handler: no_auth
            - handler: allow
            ```
            
            To fix this, you should choose only one access strategy.
            
            ```yaml
            accessStrategies:
            - handler: no_auth
            ```
            
            OR
            
            ```yaml
            accessStrategies:
            - handler: allow
            ```"""
            ),
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
            dedent(
                """
            The function fails because of an incorrect Date object constructor:

            ```javascript
            const now = new Dates(); // Wrong
            ```

            Should be:

            ```javascript
            const now = new Date(); // Correct
            ```

            Simply fix the constructor name from `Dates` to `Date` and the function will work properly.
            """
            ),
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
    should_raise,
):
    """Test the _invoke_chain method with success, context, and error scenarios."""
    if should_raise:
        with pytest.raises(expected_result):
            kyma_agent._invoke_chain(state, {})
    else:
        response = kyma_agent._invoke_chain(state, {})
        assert isinstance(response, AIMessage)

        # Test the response content
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
