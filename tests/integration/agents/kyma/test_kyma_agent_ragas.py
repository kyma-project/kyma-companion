import pytest
from deepeval import assert_test
from deepeval.metrics import (
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from ragas.dataset_schema import MultiTurnSample
from ragas.integrations.langgraph import convert_to_ragas_messages
from ragas.messages import ToolCall
from ragas.metrics._string import NonLLMStringSimilarity
from ragas.metrics._tool_call_accuracy import ToolCallAccuracy

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from integration.agents.fixtures.api_rule import (
    API_RULE_WITH_WRONG_ACCESS_STRATEGY,
    KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
)
from integration.agents.fixtures.serverless_function import (
    KYMADOC_FUNCTION_TROUBLESHOOTING,
    SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
)
from services.data_sanitizer import DataSanitizer
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from utils.settings import (
    DEEPEVAL_TESTCASE_VERBOSE,
    TEST_CLUSTER_AUTH_TOKEN,
    TEST_CLUSTER_CA_DATA,
    TEST_CLUSTER_CLIENT_CERTIFICATE_DATA,
    TEST_CLUSTER_CLIENT_KEY_DATA,
    TEST_CLUSTER_URL,
)

AGENT_STEPS_NUMBER = 25
TOOL_ACCURACY_THRESHOLD = 0.7


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


def create_k8s_client():
    data_sanitizer = DataSanitizer()
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=TEST_CLUSTER_URL,
        x_cluster_certificate_authority_data=TEST_CLUSTER_CA_DATA,
        x_k8s_authorization=TEST_CLUSTER_AUTH_TOKEN,
        x_client_certificate_data=TEST_CLUSTER_CLIENT_CERTIFICATE_DATA,
        x_client_key_data=TEST_CLUSTER_CLIENT_KEY_DATA,
    )
    # Initialize k8s client for the request.
    k8s_client: IK8sClient = K8sClient.new(
        k8s_auth_headers=k8s_auth_headers,
        data_sanitizer=data_sanitizer,
    )
    return k8s_client


@pytest.fixture
def k8s_client():
    # Initialize k8s client for the request.
    k8s_client: IK8sClient = create_k8s_client()
    return k8s_client


@pytest.fixture
def kyma_agent(app_models):
    return KymaAgent(app_models)


# Helper functions for test simplification
def create_system_message(resource_info: dict) -> SystemMessage:
    """Create a system message with resource information."""
    return SystemMessage(content=f"The user query is related to: {resource_info}")


def create_basic_state(
    task_description: str,
    messages: list = None,
    k8s_client: IK8sClient = None,
) -> KymaAgentState:
    """Create a basic KymaAgentState with common fields."""
    return KymaAgentState(
        agent_messages=[],
        messages=messages,
        subtasks=[
            {
                "description": task_description,
                "task_title": task_description,
                "assigned_to": "KymaAgent",
            }
        ],
        my_task=SubTask(
            description=task_description,
            task_title=task_description,
            assigned_to="KymaAgent",
        ),
        k8s_client=k8s_client,
        is_last_step=False,
        remaining_steps=AGENT_STEPS_NUMBER,
    )


def create_tool_call(tool_id: str, tool_name: str, args: dict) -> dict:
    """Create a standardized tool call dictionary."""
    return {
        "id": tool_id,
        "type": "tool_call",
        "name": tool_name,
        "args": args,
    }


async def assert_response(
    response: AIMessage,
    expected_tool_call: str = None,
    expected_content: str = None,
    retrieval_context: str = None,
    correctness_metric=None,
    faithfulness_metric=None,
    task_description: str = "",
):
    """Assert the response matches expected behavior."""
    assert isinstance(response, AIMessage)

    if expected_tool_call:
        # Verify tool call properties
        assert response.tool_calls is not None, "Expected tool calls but found none"
        assert len(response.tool_calls) > 0, "Expected at least one tool call"
        tool_call = response.tool_calls[0]
        assert tool_call.get("type") == "tool_call"
        assert tool_call.get("name") == expected_tool_call
    else:
        # Verify content response using deepeval metrics
        test_case = LLMTestCase(
            input=task_description,
            actual_output=response.content,
            expected_output=expected_content,
            retrieval_context=[retrieval_context] if retrieval_context else [],
        )
        assert_test(test_case, [correctness_metric, faithfulness_metric])


# Test data definitions
class TestCase:
    def __init__(
        self,
        name: str,
        state: KymaAgentState,
        expected_tool_calls: list[ToolCall] = None,
        expected_response: str = None,
        retrieval_context: str = None,
        should_raise: bool = False,
    ):
        self.name = name
        self.state = state
        self.expected_tool_calls = expected_tool_calls
        self.expected_response = expected_response
        self.retrieval_context = retrieval_context
        self.should_raise = should_raise


api_rule_resource_info = {
    "resource_api_version": "gateway.kyma-project.io/v1beta1",
    "resource_namespace": "kyma-app-apirule-broken",
}


@pytest.fixture
def api_rule_complete_state(k8s_client: IK8sClient):
    return create_basic_state(
        task_description="What is wrong with api rule?",
        messages=[
            create_system_message(api_rule_resource_info),
            HumanMessage(content="What is wrong with api rule?"),
            AIMessage(
                content="",
                tool_calls=[
                    create_tool_call(
                        "tool_call_id_1",
                        "kyma_query_tool",
                        {
                            "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/kyma-app-apirule-broken/apirules"
                        },
                    )
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
                    create_tool_call(
                        "tool_call_id_2",
                        "search_kyma_doc",
                        {"query": "APIRule validation errors"},
                    )
                ],
            ),
            ToolMessage(
                content=KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
                name="search_kyma_doc",
                tool_call_id="tool_call_id_2",
            ),
        ],
        k8s_client=k8s_client,
    )


# Serverless Function test cases


@pytest.fixture
def function_resource_info():
    return {
        "resource_kind": "Function",
        "resource_api_version": "serverless.kyma-project.io/v1alpha2",
        "resource_name": "func1",
        "resource_namespace": "kyma-app-serverless-syntax-err",
    }


@pytest.fixture
def function_complete_state(k8s_client):
    return create_basic_state(
        task_description="What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?",
        messages=[
            create_system_message(function_resource_info),
            HumanMessage(content="what is wrong?"),
            AIMessage(
                content="",
                tool_calls=[
                    create_tool_call(
                        "tool_call_id_1",
                        "kyma_query_tool",
                        {
                            "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                        },
                    )
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
                    create_tool_call(
                        "tool_call_id_2",
                        "search_kyma_doc",
                        {"query": "Kyma Function troubleshooting"},
                    )
                ],
            ),
            ToolMessage(
                content=KYMADOC_FUNCTION_TROUBLESHOOTING,
                name="search_kyma_doc",
                tool_call_id="tool_call_id_2",
            ),
        ],
        k8s_client=k8s_client,
    )


def create_test_cases(k8s_client: IK8sClient):
    """Fixture providing test cases for Kyma agent testing."""
    return [
        # Complete response test cases
        # TestCase(
        #     "Should return right solution for API Rule with wrong access strategy",
        #     api_rule_complete_state,
        #     expected_response=EXPECTED_API_RULE_RESPONSE,
        #     retrieval_context=KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
        # ),
        # TestCase(
        #     "Should return right solution for Serverless Function with syntax error",
        #     function_complete_state,
        #     expected_response=EXPECTED_SERVERLESS_FUNCTION_RESPONSE,
        # ),
        # # Tool call test cases
        # TestCase(
        #     "Should return Kyma resource query tool call for the first user query call",
        #     create_basic_state(
        #         system_content=f"The user query is related to: {api_rule_resource_info}",
        #         user_query="What is wrong with api rule?",
        #         task_description="What is wrong with api rule?",
        #     ),
        #     expected_tool_calls=[
        #         ToolCall(
        #             name="kyma_query_tool",
        #             args={
        #                 "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/kyma-app-apirule-broken/apirules"
        #             },
        #         ),
        #     ],
        # ),
        TestCase(
            "Should use Kyma Resource Query and then Kyma Doc Search Tool Calls sequentially",
            state=create_basic_state(
                task_description="What is wrong with api rules?",
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_namespace': 'sample-namespace'}"
                    ),
                    HumanMessage(content="What is wrong with api rules?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                ToolCall(
                    name="fetch_kyma_resource_version",
                    args={
                        "resource_kind": "APIRule",
                    },
                ),
                ToolCall(
                    name="kyma_query_tool",
                    args={"uri": "/apis/gateway.kyma-project.io/v1beta1/apirules"},
                ),
                ToolCall(
                    name="search_kyma_doc",
                    args={
                        "query": "APIRule multiple accessStrategies error allow no_auth"
                    },
                ),
            ],
        ),
        TestCase(
            "Should use Kyma Resource Query for a single resource and then Kyma Doc Search Tool Calls sequentially",
            state=create_basic_state(
                task_description="What is wrong with api rule?",
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'test-apirule-7', 'resource_kind': 'APIRule', 'resource_name': 'restapi'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                # ToolCall(
                #     name="fetch_kyma_resource_version",
                #     args={
                #         "resource_kind": "APIRule",
                #     },
                # ),
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/test-apirule-7/apirules/restapi"
                    },
                ),
                ToolCall(
                    name="search_kyma_doc",
                    args={
                        "query": "APIRule multiple accessStrategies error allow no_auth"
                    },
                ),
            ],
        ),
        # TestCase(
        #     "Should return Kyma Doc Search Tool Call after Kyma Resource Query Tool Call",
        #     create_basic_state(
        #         system_content=f"The user query is related to: {api_rule_resource_info}",
        #         user_query="What is wrong with api rule?",
        #         task_description="What is wrong with ApiRule?",
        #         messages=[
        #             create_system_message(api_rule_resource_info),
        #             HumanMessage(content="What is wrong with api rule?"),
        #             AIMessage(
        #                 content="",
        #                 tool_calls=[
        #                     create_tool_call(
        #                         "tool_call_id_1",
        #                         "kyma_query_tool",
        #                         {
        #                             "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/kyma-app-apirule-broken/apirules"
        #                         },
        #                     )
        #                 ],
        #             ),
        #             ToolMessage(
        #                 content=API_RULE_WITH_WRONG_ACCESS_STRATEGY,
        #                 name="kyma_query_tool",
        #                 tool_call_id="tool_call_id_1",
        #             ),
        #         ],
        #     ),
        #     expected_tool_calls=[
        #         ToolCall(
        #             name="kyma_query_tool",
        #             args={
        #                 "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/kyma-app-apirule-broken/apirules"
        #             },
        #         ),
        #         ToolCall(
        #             name="search_kyma_doc",
        #             args={"query": "APIRule validation errors"},
        #         ),
        #     ],
        # ),
        # # BTP Manager test case
        # TestCase(
        #     "Should return right solution for general Kyma question - only need Kyma Doc Search",
        #     create_basic_state(
        #         system_content="The user query is related to: {}",
        #         user_query="what are the BTP Operator features?",
        #         task_description="What are the BTP Operator features?",
        #         messages=[
        #             SystemMessage(content="The user query is related to: {}"),
        #             HumanMessage(content="what are the BTP Operator features?"),
        #             AIMessage(
        #                 content="",
        #                 tool_calls=[
        #                     create_tool_call(
        #                         "tool_call_id_1",
        #                         "search_kyma_doc",
        #                         {"query": "BTP Operator features"},
        #                     )
        #                 ],
        #             ),
        #             ToolMessage(
        #                 content=RETRIEVAL_CONTEXT,
        #                 name="search_kyma_doc",
        #                 tool_call_id="tool_call_id_1",
        #             ),
        #         ],
        #     ),
        #     expected_response=EXPECTED_BTP_MANAGER_RESPONSE,
        # ),
    ]


@pytest.fixture
def tool_accuracy_scorer():
    metric = ToolCallAccuracy()
    metric.arg_comparison_metric = NonLLMStringSimilarity()
    return metric


async def call_kyma_agent(kyma_agent, state):
    # calls kyma_agent.agent_node() which langgraph graph.
    response = await kyma_agent.agent_node().ainvoke(state)
    return response


@pytest.mark.parametrize("test_case", create_test_cases(create_k8s_client()))
@pytest.mark.asyncio
async def test_kyma_agent_invoke_chain(
    kyma_agent, tool_accuracy_scorer, test_case: TestCase
):
    """
    Simplified test for KymaAgent _invoke_chain method.
    Tests both tool calling and content response scenarios.
    """
    if test_case.should_raise:
        # TODO: add test case for should_raise
        pass
    else:
        # response = await kyma_agent._invoke_chain(test_case.state, {})
        response = await call_kyma_agent(kyma_agent, test_case.state)
        ragas_messages = convert_to_ragas_messages(response["agent_messages"])

        sample = MultiTurnSample(
            user_input=ragas_messages,
            reference_tool_calls=test_case.expected_tool_calls,
        )

        score = await tool_accuracy_scorer.multi_turn_ascore(sample)
        assert (
            score > TOOL_ACCURACY_THRESHOLD
        ), f"Tool call accuracy ({score:.2f}) is below the acceptable threshold of {TOOL_ACCURACY_THRESHOLD}"
