import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from ragas.dataset_schema import MultiTurnSample
from ragas.integrations.langgraph import convert_to_ragas_messages
from ragas.messages import ToolCall
from ragas.metrics._string import NonLLMStringSimilarity
from ragas.metrics._tool_call_accuracy import ToolCallAccuracy

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from services.data_sanitizer import DataSanitizer
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from utils.settings import (
    TEST_CLUSTER_AUTH_TOKEN,
    TEST_CLUSTER_CA_DATA,
    TEST_CLUSTER_CLIENT_CERTIFICATE_DATA,
    TEST_CLUSTER_CLIENT_KEY_DATA,
    TEST_CLUSTER_URL,
)

AGENT_STEPS_NUMBER = 25
TOOL_ACCURACY_THRESHOLD = 0.5


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


@pytest.fixture
def tool_accuracy_scorer():
    metric = ToolCallAccuracy()
    metric.arg_comparison_metric = NonLLMStringSimilarity()
    return metric


async def call_kyma_agent(kyma_agent, state):
    # Invokes kyma agent subgraph.
    response = await kyma_agent.agent_node().ainvoke(state)
    return response


def create_test_cases_kyma_knowledge(k8s_client: IK8sClient):
    """Fixture providing test cases for Kyma agent testing."""
    return [
        TestCase(
            "Should call kyma doc search tool for general Kyma knowledge",
            state=create_basic_state(
                task_description="what is Kyma?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'eventing.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Function', 'resource_name': 'func1', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="what is Kyma?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                ToolCall(
                    name="search_kyma_doc",
                    args={"query": "what is Kyma?"},
                ),
            ],
        ),
        TestCase(
            "Should call kyma doc search tool for Kyma module enablement",
            state=create_basic_state(
                task_description="how to enable a module?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'eventing.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Function', 'resource_name': 'func1', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="how to enable a module?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                ToolCall(
                    name="search_kyma_doc",
                    args={"query": "how to enable a module?"},
                ),
            ],
        ),
    ]


@pytest.mark.parametrize(
    "test_case", create_test_cases_kyma_knowledge(create_k8s_client())
)
@pytest.mark.asyncio
async def test_kyma_agent_kyma_knowledge(
    kyma_agent, tool_accuracy_scorer, test_case: TestCase
):
    agent_response = await call_kyma_agent(kyma_agent, test_case.state)
    agent_messages = convert_to_ragas_messages(agent_response["agent_messages"])

    test_case_sample = MultiTurnSample(
        user_input=agent_messages,
        reference_tool_calls=test_case.expected_tool_calls,
    )

    score = await tool_accuracy_scorer.multi_turn_ascore(test_case_sample)
    assert (
        score > TOOL_ACCURACY_THRESHOLD
    ), f"Tool call accuracy ({score:.2f}) is below the acceptable threshold of {TOOL_ACCURACY_THRESHOLD}"


def create_test_cases_namespace_scoped(k8s_client: IK8sClient):
    """Fixture providing test cases for Kyma agent testing."""
    return [
        TestCase(
            "Should not call fetch_kyma_resource_version tool call as Subscription resource version is correct",
            state=create_basic_state(
                task_description="is there any issue?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'eventing.kyma-project.io/v1alpha2', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Subscription', 'resource_name': 'sub1', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="is there any issue?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                # no fetch_kyma_resource_version tool call as resource_api_version is correctly provided
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/eventing.kyma-project.io/v1alpha2/namespaces/test-function-8/subscriptions/sub1"
                    },
                ),
                # should search kyma doc as there is Kyma Subscription validation error
                ToolCall(
                    name="search_kyma_doc",
                    args={"query": "Subscription validation errors"},
                ),
            ],
        ),
        TestCase(
            "Should not call kyma doc search tool as Function has JavaScript issue",
            state=create_basic_state(
                task_description="is there any issue?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'serverless.kyma-project.io/v1alpha2', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Function', 'resource_name': 'func1', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="is there any issue?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                # no fetch_kyma_resource_version tool call as resource_api_version is correctly provided
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/test-function-8/functions/func1"
                    },
                ),
            ],
        ),
        TestCase(
            "Should not call kyma doc search tool as Function is successfully deployed",
            state=create_basic_state(
                task_description="check for errors?",
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'serverless.kyma-project.io/v1alpha2', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Function', 'resource_name': 'func1', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="check for errors?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                # only retrieves function as function is successfully deployed
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/test-function-8/functions/func1"
                    },
                ),
            ],
        ),
        TestCase(
            "Should call fetch_kyma_resource_version tool call if kyma_query_tool call fails",
            state=create_basic_state(
                task_description="What is wrong with api rules?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v2', "
                        "'resource_namespace': 'test-apirule-7', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="What is wrong with api rules?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                # kyma_query_tool call fails as 'gateway.kyma-project.io/v2' is not available in the cluster
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/gateway.kyma-project.io/v2/namespaces/test-apirule-7/apirules"
                    },
                ),
                # after kyma_query_tool call fails, fetch_kyma_resource_version tool call is used for correct version
                ToolCall(
                    name="fetch_kyma_resource_version",
                    args={
                        "resource_kind": "APIRule",
                    },
                ),
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/test-apirule-7/apirules"
                    },
                ),
                ToolCall(
                    name="search_kyma_doc",
                    args={
                        "query": "APIRule validation errors allow no_auth access strategy combination"
                    },
                ),
            ],
        ),
        TestCase(
            "Should not call fetch_kyma_resource_version tool call if kyma_query_tool call succeeds",
            state=create_basic_state(
                task_description="What is wrong with api rule?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-apirule-7', 'resource_kind': 'APIRule', 'resource_name': 'restapi', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                # no fetch_kyma_resource_version tool call as resource_api_version is correctly provided
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/test-apirule-7/apirules/restapi"
                    },
                ),
                # should search kyma doc as there is Kyma APIRule access strategies error
                ToolCall(
                    name="search_kyma_doc",
                    args={
                        "query": "APIRule validation error allow no_auth access strategy combination"
                    },
                ),
            ],
        ),
        TestCase(
            "Should call fetch Subscription resource version tool call as provided resource_api_version is wrong",
            state=create_basic_state(
                task_description="is there any issue?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'eventing.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Subscription', 'resource_name': 'sub1', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="is there any issue?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/eventing.kyma-project.io/v1beta1/namespaces/test-function-8/subscriptions/sub1"
                    },
                ),
                # fetch_kyma_resource_version tool call as resource_api_version is wrong
                ToolCall(
                    name="fetch_kyma_resource_version",
                    args={
                        "resource_kind": "Function",
                    },
                ),
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/eventing.kyma-project.io/v1alpha2/namespaces/test-function-8/subscriptions/sub1"
                    },
                ),
                ToolCall(
                    name="search_kyma_doc",
                    args={"query": "Subscription validation errors"},
                ),
            ],
        ),
        TestCase(
            "Should use Function resource type from the user query, not APIRule from the system message",
            state=create_basic_state(
                task_description="What is wrong with function in namespace test-function-18?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-apirule-7', 'resource_kind': 'APIRule', 'resource_name': 'restapi', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(
                        content="What is wrong with function in namespace test-function-18?"
                    ),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                # fetch_kyma_resource_version tool call as different resource mentioned in the user query
                ToolCall(
                    name="fetch_kyma_resource_version",
                    args={
                        "resource_kind": "Function",
                    },
                ),
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/test-function-18/functions/func1"
                    },
                ),
                # search kyma doc as there is Kyma function spec issue
                ToolCall(
                    name="search_kyma_doc",
                    args={"query": "Function invalid dependencies troubleshooting"},
                ),
            ],
        ),
    ]


@pytest.mark.parametrize(
    "test_case", create_test_cases_namespace_scoped(create_k8s_client())
)
@pytest.mark.asyncio
async def test_kyma_agent_namespace_scoped(
    kyma_agent, tool_accuracy_scorer, test_case: TestCase
):
    agent_response = await call_kyma_agent(kyma_agent, test_case.state)
    agent_messages = convert_to_ragas_messages(agent_response["agent_messages"])

    test_case_sample = MultiTurnSample(
        user_input=agent_messages,
        reference_tool_calls=test_case.expected_tool_calls,
    )

    score = await tool_accuracy_scorer.multi_turn_ascore(test_case_sample)
    assert (
        score > TOOL_ACCURACY_THRESHOLD
    ), f"{test_case.name}: Tool call accuracy ({score:.2f}) is below the threshold of {TOOL_ACCURACY_THRESHOLD}"


def create_test_cases_cluster_scoped(k8s_client: IK8sClient):
    """Fixture providing test cases for Kyma agent testing."""
    return [
        TestCase(
            "Should use Kyma Resource Query and then Kyma Doc Search Tool Calls sequentially",
            state=create_basic_state(
                task_description="What is wrong with api rules?",
                messages=[
                    SystemMessage(content="{'resource_namespace': 'test-apirule-7'}"),
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
                    args={
                        "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/test-apirule-7/apirules"
                    },
                ),
                ToolCall(
                    name="search_kyma_doc",
                    args={
                        "query": "APIRule validation error allow no_auth access strategy combination"
                    },
                ),
            ],
        ),
        TestCase(
            "Should use cluster scope retrieval with kyma query tool",
            state=create_basic_state(
                task_description="check all subscriptions in the cluster",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-apirule-7', 'resource_kind': 'APIRule', 'resource_name': 'restapi'}"
                    ),
                    HumanMessage(content="check all subscriptions in the cluster"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[
                ToolCall(
                    name="fetch_kyma_resource_version",
                    args={
                        "resource_kind": "Subscription",
                    },
                ),
                ToolCall(
                    name="kyma_query_tool",
                    args={
                        "uri": "/apis/eventing.kyma-project.io/v1alpha2/subscriptions"
                    },
                ),
            ],
        ),
        TestCase(
            "Should use cluster scope retrieval with kyma query tool",
            state=create_basic_state(
                task_description="check all resources in the cluster",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-apirule-7', 'resource_kind': 'APIRule', 'resource_name': 'restapi'}"
                    ),
                    HumanMessage(content="check all resources in the cluster"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[],
        ),
        TestCase(
            "Should use cluster scope retrieval with kyma query tool",
            state=create_basic_state(
                task_description="show me all Kyma resources",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-apirule-7', 'resource_kind': 'APIRule', 'resource_name': 'restapi'}"
                    ),
                    HumanMessage(content="what is wrong with Kyma?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_tool_calls=[],
        ),
    ]


@pytest.mark.parametrize(
    "test_case", create_test_cases_cluster_scoped(create_k8s_client())
)
@pytest.mark.asyncio
async def test_kyma_agent_cluster_scoped(
    kyma_agent, tool_accuracy_scorer, test_case: TestCase
):
    response = await call_kyma_agent(kyma_agent, test_case.state)
    ragas_messages = convert_to_ragas_messages(response["agent_messages"])

    if test_case.expected_tool_calls == []:
        assert len(response["agent_messages"]) == 1
    else:
        test_case_sample = MultiTurnSample(
            user_input=ragas_messages,
            reference_tool_calls=test_case.expected_tool_calls,
        )

        score = await tool_accuracy_scorer.multi_turn_ascore(test_case_sample)
        assert (
            score > TOOL_ACCURACY_THRESHOLD
        ), f"Tool call accuracy ({score:.2f}) is below the acceptable threshold of {TOOL_ACCURACY_THRESHOLD}"
