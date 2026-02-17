from dataclasses import dataclass, field

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
EXPECTED_MAX_RETRY_ATTEMPTS = 5

# Tool name constants
TOOL_KYMA_QUERY = "kyma_query_tool"
TOOL_FETCH_KYMA_VERSION = "fetch_kyma_resource_version"
TOOL_SEARCH_KYMA_DOC = "search_kyma_doc"


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


@dataclass
class TestCase:
    name: str
    state: KymaAgentState
    expected_tool_calls: list[ToolCall] | None = None
    alternative_tool_calls: list[list[ToolCall]] = field(default_factory=list)
    expected_response: str | None = None
    retrieval_context: str | None = None
    should_raise: bool = False


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


@pytest.mark.parametrize("test_case", create_test_cases_kyma_knowledge(create_k8s_client()), ids=lambda tc: tc.name)
@pytest.mark.asyncio
async def test_kyma_agent_kyma_knowledge(kyma_agent, tool_accuracy_scorer, test_case: TestCase):
    agent_response = await call_kyma_agent(kyma_agent, test_case.state)
    agent_messages = convert_to_ragas_messages(agent_response["agent_messages"])

    test_case_sample = MultiTurnSample(
        user_input=agent_messages,
        reference_tool_calls=test_case.expected_tool_calls,
    )

    score = await tool_accuracy_scorer.multi_turn_ascore(test_case_sample)
    assert score > TOOL_ACCURACY_THRESHOLD, (
        f"Tool call accuracy ({score:.2f}) is below the acceptable threshold of {TOOL_ACCURACY_THRESHOLD}"
    )



@dataclass
class NamespaceScopedTestCase:
    """Test case for namespace-scoped agent testing with invariants."""

    name: str
    state: KymaAgentState
    # Required invariants
    must_call_tools: list[str] = field(default_factory=list)  # Tools that MUST be called
    must_not_call_tools: list[str] = field(default_factory=list)  # Tools that must NOT be called
    must_contain_in_messages: list[str] = field(default_factory=list)  # Strings that must appear in messages
    must_not_contain_in_messages: list[str] = field(default_factory=list)  # Strings that must NOT appear
    max_tool_call_count: dict[str, int] = field(default_factory=dict)  # Max count per tool name


def extract_tool_call_info(agent_messages):
    """Extract tool call names and content from agent messages."""
    tool_call_names = []
    all_content = []

    for msg in agent_messages:
        # Collect tool call names
        if hasattr(msg, "name") and msg.name:
            tool_call_names.append(msg.name)
        elif hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if isinstance(tc, dict) and tc.get("name"):
                    tool_call_names.append(tc.get("name"))
                elif hasattr(tc, "name") and tc.name:
                    tool_call_names.append(tc.name)

        # Collect all message content for version checking
        if hasattr(msg, "content"):
            all_content.append(str(msg.content))
        if hasattr(msg, "additional_kwargs"):
            all_content.append(str(msg.additional_kwargs))

    return tool_call_names, all_content


def assert_outcome_invariants(test_case: NamespaceScopedTestCase, agent_messages: list):
    """Assert all invariants for a namespace-scoped test case."""
    tool_call_names, all_content = extract_tool_call_info(agent_messages)
    messages_str = " ".join(all_content)

    # Check required tools were called
    for tool_name in test_case.must_call_tools:
        assert tool_name in tool_call_names, f"Expected tool '{tool_name}' to be called but it wasn't"

    # Check forbidden tools were NOT called
    for tool_name in test_case.must_not_call_tools:
        assert tool_name not in tool_call_names, f"Tool '{tool_name}' should NOT have been called but it was"

    # Check required content appears in messages
    for content in test_case.must_contain_in_messages:
        assert content in messages_str, f"Expected '{content}' in messages but didn't find it"

    # Check forbidden content does NOT appear
    for content in test_case.must_not_contain_in_messages:
        assert content not in messages_str, f"'{content}' should NOT appear in messages but it did"

    # Check tool call counts don't exceed maximums
    for tool_name, max_count in test_case.max_tool_call_count.items():
        actual_count = tool_call_names.count(tool_name)
        assert actual_count <= max_count, f"Tool '{tool_name}' called {actual_count} times, exceeds max of {max_count}"


def create_test_cases_namespace_scoped(k8s_client: IK8sClient):
    """Create table of namespace-scoped test cases with invariants."""
    return [
        NamespaceScopedTestCase(
            name="Should handle wrong Subscription API version and correct it",
            state=create_basic_state(
                task_description="is there any issue?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'eventing.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Subscription', "
                        "'resource_name': 'sub1', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="is there any issue?"),
                ],
                k8s_client=k8s_client,
            ),
            must_call_tools=[TOOL_KYMA_QUERY, TOOL_FETCH_KYMA_VERSION],
            must_contain_in_messages=["v1alpha2"],  # Must eventually use correct version
            max_tool_call_count={TOOL_KYMA_QUERY: EXPECTED_MAX_RETRY_ATTEMPTS},
        ),
        NamespaceScopedTestCase(
            name="Should handle correct Function API version without fetching version",
            state=create_basic_state(
                task_description="is there any issue?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'serverless.kyma-project.io/v1alpha2', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Function', "
                        "'resource_name': 'func1', 'resource_scope': 'namespaced'}"
                    ),
                    HumanMessage(content="is there any issue?"),
                ],
                k8s_client=k8s_client,
            ),
            must_call_tools=[TOOL_KYMA_QUERY],
            must_not_call_tools=[TOOL_FETCH_KYMA_VERSION],  # Version is correct, no need to fetch
            must_contain_in_messages=["v1alpha2"],
        ),
        NamespaceScopedTestCase(
            name="Should handle wrong APIRule version (v2) and correct to v1beta1",
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
            must_call_tools=[TOOL_KYMA_QUERY, TOOL_FETCH_KYMA_VERSION],
            must_contain_in_messages=["v1beta1"],  # Must correct to v1beta1
            max_tool_call_count={TOOL_KYMA_QUERY: EXPECTED_MAX_RETRY_ATTEMPTS},
        ),
    ]


@pytest.mark.parametrize(
    "test_case",
    create_test_cases_namespace_scoped(create_k8s_client()),
    ids=lambda tc: tc.name,
)
@pytest.mark.asyncio
async def test_kyma_agent_namespace_scoped(kyma_agent, test_case: NamespaceScopedTestCase):
    """Test agent behavior by verifying outcomes and invariants."""
    # When: Agent processes the request
    result = await call_kyma_agent(kyma_agent, test_case.state)

    # Then: Agent should have made tool calls
    agent_messages = result.get("agent_messages", [])
    assert len(agent_messages) > 0, "Agent should have made tool calls"

    # Then: Assert all invariants defined in the test case
    assert_outcome_invariants(test_case, agent_messages)


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
                    args={"uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/test-apirule-7/apirules"},
                ),
                ToolCall(
                    name="search_kyma_doc",
                    args={"query": "APIRule validation error allow no_auth access strategy combination"},
                ),
            ],
            alternative_tool_calls=[
                # Alternative: If no errors found in APIRule, agent may not search docs
                [
                    ToolCall(
                        name="fetch_kyma_resource_version",
                        args={
                            "resource_kind": "APIRule",
                        },
                    ),
                    ToolCall(
                        name="kyma_query_tool",
                        args={"uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/test-apirule-7/apirules"},
                    ),
                ],
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
                    args={"uri": "/apis/eventing.kyma-project.io/v1alpha2/subscriptions"},
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


@pytest.mark.parametrize("test_case", create_test_cases_cluster_scoped(create_k8s_client()), ids=lambda tc: tc.name)
@pytest.mark.asyncio
async def test_kyma_agent_cluster_scoped(kyma_agent, tool_accuracy_scorer, test_case: TestCase):
    response = await call_kyma_agent(kyma_agent, test_case.state)
    ragas_messages = convert_to_ragas_messages(response["agent_messages"])

    if test_case.expected_tool_calls == []:
        assert len(response["agent_messages"]) == 1
    else:
        # Try primary expected tool calls first
        test_case_sample = MultiTurnSample(
            user_input=ragas_messages,
            reference_tool_calls=test_case.expected_tool_calls,
        )
        score = await tool_accuracy_scorer.multi_turn_ascore(test_case_sample)

        # If primary fails and alternatives exist, try them
        if score <= TOOL_ACCURACY_THRESHOLD and test_case.alternative_tool_calls:
            for alt_calls in test_case.alternative_tool_calls:
                alt_sample = MultiTurnSample(
                    user_input=ragas_messages,
                    reference_tool_calls=alt_calls,
                )
                alt_score = await tool_accuracy_scorer.multi_turn_ascore(alt_sample)
                if alt_score > TOOL_ACCURACY_THRESHOLD:
                    score = alt_score
                    break

        assert score > TOOL_ACCURACY_THRESHOLD, (
            f"{test_case.name}: Tool call accuracy ({score:.2f}) is below the threshold of {TOOL_ACCURACY_THRESHOLD}"
        )
