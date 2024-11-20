from textwrap import dedent
from unittest.mock import Mock

import pytest
from deepeval import evaluate
from deepeval.metrics import (
    FaithfulnessMetric,
    GEval,
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
from utils.settings import DEEPEVAL_TESTCASE_VERBOSE


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


@pytest.mark.parametrize(
    "test_case,state,retrieval_context,expected_result,expected_tool_call,should_raise",
    [
        # Test case for API Rule with wrong access strategy
        # - Verifies agent correctly identifies and explains API Rule validation error
        # - Checks agent uses both kyma_query_tool and search_kyma_doc
        # - Validates response matches expected explanation about multiple access strategies
        (
            "Should return right solution for API Rule with wrong access strategy",
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
                                "name": "search_kyma_doc",
                                "args": {"query": "APIRule validation errors"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content=KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="What is wrong with API rule?", assigned_to="KymaAgent"
                ),
                k8s_client=Mock(spec_set=IK8sClient),
                is_last_step=False,
            ),
            KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
            EXPECTED_API_RULE_RESPONSE,
            None,
            False,
        ),
        # Test case for initial API Rule query
        # - Verifies agent makes correct kyma_query_tool call on first interaction
        (
            "Should return Kyma resource query tool call for the first user query call",
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
            EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
            "kyma_query_tool",
            False,
        ),
        # Test case for API Rule documentation search
        # - Verifies agent searches Kyma docs after getting API Rule resource
        # - Validates proper sequence of tool calls (query then doc search)
        (
            "Should return Kyma Doc Search Tool Call after Kyma Resource Query Tool Call",
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
            EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
            "search_kyma_doc",
            False,
        ),
        # Test case for Serverless Function with syntax error
        # - Verifies agent correctly identifies JavaScript syntax error
        # - Validates response includes proper error explanation
        (
            "Should return right solution for Serverless Function with syntax error",
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
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "Kyma Function troubleshooting"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content=KYMADOC_FUNCTION_TROUBLESHOOTING,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),  # context
            None,  # retrieval_context
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE,  # expected_result
            None,  # expected_tool_call
            False,  # should_raise
        ),
        # Test case for Serverless Function with no replicas
        # - Verifies agent detects and explains replica configuration issue
        # - Validates response includes proper explanation about replica requirements
        (
            "Should return right solution for Serverless Function with no replicas",
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
                                "name": "search_kyma_doc",
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
                        name="search_kyma_doc",
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
            None,
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE_NO_REPLICAS,
            None,
            False,
        ),
        # Test case for general Kyma documentation query
        # - Verifies agent handles general documentation queries without resource lookup
        # - Checks proper use of doc search tool for BTP Operator features
        # - Validates response matches expected documentation content
        (
            "Should return right solution for general Kyma question - only need Kyma Doc Search",
            KymaAgentState(
                messages=[
                    AIMessage(content="The user query is related to: {}"),
                    HumanMessage(content="what are the BTP Operator features?"),
                    AIMessage(
                        content='```json\n{ "subtasks": [ { "description": "what are the BTP Operator features?", "assigned_to": "KymaAgent" } ] }\n```',
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
                                "name": "search_kyma_doc",
                                "args": {"query": "BTP Operator features"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content=RETRIEVAL_CONTEXT,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="What are the BTP Operator features?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            "",
            EXPECTED_BTP_MANAGER_RESPONSE,
            None,
            False,
        ),
        # Test case for Kyma doc search when no relevant documentation is found
        # - it still responds with the existing knowledge as BTP Operator features are known to LLM
        (
            "Should make kyma doc tool search once when no relevant documentation is found",
            KymaAgentState(
                messages=[
                    AIMessage(content="The user query is related to: {}"),
                    HumanMessage(content="what are the BTP Operator features?"),
                    AIMessage(
                        content='```json\n{ "subtasks": [ { "description": "what are the BTP Operator features?", "assigned_to": "KymaAgent" } ] }\n```',
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
                                "name": "search_kyma_doc",
                                "args": {"query": "BTP Operator features"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content="No relevant documentation found.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[],
                my_task=SubTask(
                    description="What are the BTP Operator features?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
            ),
            "",
            "I couldn't find specific documentation on the features of the BTP Operator in the Kyma documentation. "
            "However, generally, the BTP Operator in Kyma is responsible for managing the lifecycle of "
            "SAP BTP service instances and bindings. It integrates SAP BTP services into the Kyma environment, "
            "allowing you to provision and bind services from the SAP Business Technology Platform."
            "If you have specific questions or need further details, you might want to check the official "
            "SAP BTP documentation or resources related to the BTP Operator for more comprehensive information.",
            None,
            False,
        ),
    ],
)
def test_invoke_chain(
    kyma_agent,
    correctness_metric,
    faithfulness_metric,
    test_case,
    state,
    retrieval_context,
    expected_result,
    expected_tool_call,
    should_raise,
):
    if should_raise:
        # When error is expected
        with pytest.raises(expected_result):
            kyma_agent._invoke_chain(state, {})
    else:
        # When
        response = kyma_agent._invoke_chain(state, {})
        assert isinstance(response, AIMessage)

        # Then
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
                retrieval_context=([retrieval_context] if retrieval_context else []),
            )

            # Run deepeval metrics
            results = evaluate(
                test_cases=[test_case],
                metrics=[
                    correctness_metric,
                    faithfulness_metric,
                ],
            )

            # Assert all metrics pass
            assert all(
                result.success for result in results.test_results
            ), "Not all metrics passed"
