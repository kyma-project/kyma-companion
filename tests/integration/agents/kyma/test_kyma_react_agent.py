"""Integration tests for KymaReActAgent.

Tests the standalone ReAct agent that wraps Kyma tools without
supervisor/subgraph/LangGraph state machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import SimpleCriteriaScore

from agents.kyma.react_agent import KymaReActAgent, UINavigationContext
from integration.agents.fixtures.btp_manager import (
    EXPECTED_BTP_MANAGER_RESPONSE,
)
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from utils.settings import (
    MAIN_MODEL_NAME,
    TEST_CLUSTER_AUTH_TOKEN,
    TEST_CLUSTER_CA_DATA,
    TEST_CLUSTER_CLIENT_CERTIFICATE_DATA,
    TEST_CLUSTER_CLIENT_KEY_DATA,
    TEST_CLUSTER_URL,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOL_KYMA_QUERY = "kyma_query_tool"
TOOL_FETCH_KYMA_VERSION = "fetch_kyma_resource_version"
TOOL_SEARCH_KYMA_DOC = "search_kyma_doc"
TOOL_K8S_OVERVIEW = "k8s_overview_tool"
TOOL_FETCH_POD_LOGS = "fetch_pod_logs_tool"

GOAL_ACCURACY_THRESHOLD = 7
CORRECTNESS_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# ToolTrackingCallbackHandler — records tool invocations during agent execution
# ---------------------------------------------------------------------------


class ToolTrackingCallbackHandler(BaseCallbackHandler):
    """Records tool invocations during agent execution for assertion in tests."""

    def __init__(self) -> None:
        super().__init__()
        self.tool_calls: list[dict[str, Any]] = []

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> None:
        """Record each tool invocation with name and input."""
        self.tool_calls.append(
            {
                "name": serialized.get("name", ""),
                "input": input_str,
            }
        )

    @property
    def tool_names(self) -> list[str]:
        """Return the ordered list of tool names that were called."""
        return [tc["name"] for tc in self.tool_calls]


# ---------------------------------------------------------------------------
# Test Case Dataclass
# ---------------------------------------------------------------------------


@dataclass
class ReactAgentTestCase:
    """Test case for KymaReActAgent integration testing."""

    name: str
    query: str
    ui_context: UINavigationContext | None = None
    chat_history: list[BaseMessage] | None = None
    # Tool assertions
    must_call_tools: list[str] = field(default_factory=list)
    must_not_call_tools: list[str] = field(default_factory=list)
    max_tool_calls: int = 10
    expected_order: list[str] | None = None
    # Response assertions
    expected_goal: str = ""
    min_response_length: int = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_k8s_client() -> IK8sClient:
    """Create a real K8sClient from test cluster environment variables."""
    from services.data_sanitizer import DataSanitizer

    data_sanitizer = DataSanitizer()
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=TEST_CLUSTER_URL,
        x_cluster_certificate_authority_data=TEST_CLUSTER_CA_DATA,
        x_k8s_authorization=TEST_CLUSTER_AUTH_TOKEN,
        x_client_certificate_data=TEST_CLUSTER_CLIENT_CERTIFICATE_DATA,
        x_client_key_data=TEST_CLUSTER_CLIENT_KEY_DATA,
    )
    return K8sClient.new(
        k8s_auth_headers=k8s_auth_headers,
        data_sanitizer=data_sanitizer,
    )


def is_subsequence(subseq: list[str], full: list[str]) -> bool:
    """Check if subseq appears as a subsequence (not necessarily contiguous) of full."""
    it = iter(full)
    return all(item in it for item in subseq)


def assert_tool_invariants(test_case: ReactAgentTestCase, tracker: ToolTrackingCallbackHandler) -> None:
    """Assert all tool-related invariants for a test case."""
    tool_names = tracker.tool_names

    # Required tools MUST appear
    for tool_name in test_case.must_call_tools:
        assert tool_name in tool_names, (
            f"Expected tool '{tool_name}' to be called but it wasn't. Actual calls: {tool_names}"
        )

    # Forbidden tools must NOT appear
    for tool_name in test_case.must_not_call_tools:
        assert tool_name not in tool_names, (
            f"Tool '{tool_name}' should NOT have been called but it was. Actual calls: {tool_names}"
        )

    # Total tool call count does not exceed max (detect infinite loops)
    assert len(tracker.tool_calls) <= test_case.max_tool_calls, (
        f"Too many tool calls ({len(tracker.tool_calls)} > {test_case.max_tool_calls}). "
        f"Possible retry loop. Calls: {tool_names}"
    )

    # Order check (when strict ordering matters)
    if test_case.expected_order:
        assert is_subsequence(test_case.expected_order, tool_names), (
            f"Expected tool order {test_case.expected_order} not found as subsequence in {tool_names}"
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_k8s_client():
    """Create a mocked K8s client."""
    return Mock(spec_set=IK8sClient)


@pytest.fixture
def k8s_client():
    """Create a real K8s client connected to the test cluster."""
    return create_k8s_client()


@pytest.fixture
def react_agent(app_models, k8s_client):
    """Create a KymaReActAgent with a real K8s client."""
    return KymaReActAgent(models=app_models, k8s_client=k8s_client)


@pytest.fixture
def react_agent_mocked(app_models, mock_k8s_client):
    """Create a KymaReActAgent with a mocked K8s client."""
    return KymaReActAgent(models=app_models, k8s_client=mock_k8s_client)


@pytest.fixture
def tool_tracker():
    """Fresh ToolTrackingCallbackHandler for each test."""
    return ToolTrackingCallbackHandler()


@pytest.fixture
def correctness_metric(evaluator_model):
    """GEval correctness metric (same config as test_kyma_agent.py)."""
    return GEval(
        name="Correctness",
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        evaluation_steps=[
            "Evaluate whether two answers are semantically similar or convey the same meaning.",
            "Check whether the facts in 'actual output' contradict any facts in 'expected output'",
            "Lightly penalize omissions of detail, focusing on the main idea",
            "Vague language are permissible",
        ],
        model=evaluator_model,
        threshold=CORRECTNESS_THRESHOLD,
    )


@pytest.fixture
def evaluator_llm(app_models):
    """LangChain LLM wrapper for ragas evaluation."""
    main_model = app_models[MAIN_MODEL_NAME]
    return LangchainLLMWrapper(main_model.llm)


@pytest.fixture
def goal_accuracy_metric(evaluator_llm):
    """Ragas SimpleCriteriaScore for goal accuracy (same as goal_accuracy test)."""
    return SimpleCriteriaScore(
        name="course_grained_score",
        definition="Score 0 to 10 by similarity",
        llm=evaluator_llm,
    )


# ---------------------------------------------------------------------------
# 1. Basic Invocation & Response Quality
# ---------------------------------------------------------------------------

BASIC_INVOCATION_TEST_CASES = [
    ReactAgentTestCase(
        name="General Kyma knowledge query - BTP Operator features",
        query="What are the BTP Operator features?",
        expected_goal=EXPECTED_BTP_MANAGER_RESPONSE,
        min_response_length=50,
    ),
    ReactAgentTestCase(
        name="Doc search query - How to create an API Rule",
        query="How to create an API Rule in Kyma?",
        expected_goal="To create an API Rule in Kyma, define an APIRule custom resource with the gateway, host, service, and rules configuration.",
        min_response_length=50,
    ),
    ReactAgentTestCase(
        name="Module enablement query",
        query="How to enable a Kyma module?",
        expected_goal="To enable a Kyma module, add it to the Kyma custom resource modules list or use the Kyma dashboard.",
        min_response_length=50,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    BASIC_INVOCATION_TEST_CASES,
    ids=[tc.name for tc in BASIC_INVOCATION_TEST_CASES],
)
@pytest.mark.asyncio
async def test_ainvoke_basic(react_agent, correctness_metric, test_case: ReactAgentTestCase):
    """Verify ainvoke returns a quality string answer for common queries."""
    result = await react_agent.ainvoke(
        query=test_case.query,
        chat_history=test_case.chat_history,
        ui_context=test_case.ui_context,
    )

    # Basic assertions
    assert isinstance(result, str)
    assert len(result) >= test_case.min_response_length, f"Response too short ({len(result)} chars): {result[:100]}"

    # Semantic correctness evaluation
    test_case_eval = LLMTestCase(
        input=test_case.query,
        actual_output=result,
        expected_output=test_case.expected_goal,
    )
    assert_test(test_case_eval, [correctness_metric])


# ---------------------------------------------------------------------------
# 2. Tool Selection Accuracy
# ---------------------------------------------------------------------------


def create_tool_selection_test_cases() -> list[ReactAgentTestCase]:
    """Create test cases for tool selection verification."""
    return [
        ReactAgentTestCase(
            name="Resource-specific query should call kyma_query_tool",
            query="What is the status of function func1 in namespace test-function-8?",
            ui_context=UINavigationContext(
                resource_kind="Function",
                resource_name="func1",
                namespace="test-function-8",
                resource_api_version="serverless.kyma-project.io/v1alpha2",
            ),
            must_call_tools=[TOOL_KYMA_QUERY],
            max_tool_calls=5,
        ),
        ReactAgentTestCase(
            name="Doc-only query should call search_kyma_doc",
            query="What are best practices for Kyma Functions?",
            must_call_tools=[TOOL_SEARCH_KYMA_DOC],
            must_not_call_tools=[TOOL_KYMA_QUERY, TOOL_K8S_OVERVIEW],
            max_tool_calls=3,
        ),
        ReactAgentTestCase(
            name="Namespace overview should call k8s_overview_tool",
            query="Give me an overview of namespace test-function-8",
            must_call_tools=[TOOL_K8S_OVERVIEW],
            max_tool_calls=3,
        ),
        ReactAgentTestCase(
            name="General question should not call cluster tools",
            query="What is Kyma?",
            must_call_tools=[TOOL_SEARCH_KYMA_DOC],
            must_not_call_tools=[TOOL_KYMA_QUERY, TOOL_K8S_OVERVIEW, TOOL_FETCH_POD_LOGS],
            max_tool_calls=3,
        ),
        ReactAgentTestCase(
            name="should call only kyma_query_tool when problem is not kyma related",
            query="What is wrong with function func1 and how to fix it?",
            ui_context=UINavigationContext(
                resource_kind="Function",
                resource_name="func1",
                namespace="test-function-8",
                resource_api_version="serverless.kyma-project.io/v1alpha2",
            ),
            must_call_tools=[TOOL_KYMA_QUERY],
            must_not_call_tools=[TOOL_SEARCH_KYMA_DOC],
            max_tool_calls=3,
        ),
    ]


TOOL_SELECTION_TEST_CASES = create_tool_selection_test_cases()


@pytest.mark.parametrize(
    "test_case",
    TOOL_SELECTION_TEST_CASES,
    ids=[tc.name for tc in TOOL_SELECTION_TEST_CASES],
)
@pytest.mark.asyncio
async def test_tool_selection(react_agent, tool_tracker, test_case: ReactAgentTestCase):
    """Verify the agent selects correct tools — detects prompt regressions."""
    result = await react_agent.ainvoke(
        query=test_case.query,
        chat_history=test_case.chat_history,
        ui_context=test_case.ui_context,
        callbacks=[tool_tracker],
    )

    # Response must be non-empty
    assert isinstance(result, str)
    assert len(result) > 0, "Agent returned empty response"

    # Assert tool invariants
    assert_tool_invariants(test_case, tool_tracker)


# ---------------------------------------------------------------------------
# 3. UINavigationContext Handling
# ---------------------------------------------------------------------------


UI_CONTEXT_TEST_CASES = [
    ReactAgentTestCase(
        name="No context - agent uses doc search for general question",
        query="What is wrong with Kyma?",
        ui_context=None,
        expected_goal="Agent response should explain that the query is broad and ask for specific details like resource name, namespace, or kind.",
        max_tool_calls=5,
    ),
    ReactAgentTestCase(
        name="Context used when relevant - investigates specific Function",
        query="What is wrong?",
        ui_context=UINavigationContext(
            resource_kind="Function",
            resource_name="func1",
            namespace="test-function-8",
            resource_api_version="serverless.kyma-project.io/v1alpha2",
        ),
        must_call_tools=[TOOL_KYMA_QUERY],
        expected_goal="There is a syntax error in the JavaScript code. Date must be used instead of Dates.",
        max_tool_calls=6,
    ),
    ReactAgentTestCase(
        name="Context ignored when irrelevant to query",
        query="What are the BTP Operator features?",
        ui_context=UINavigationContext(
            resource_kind="Pod",
            resource_name="nginx",
            namespace="default",
        ),
        must_call_tools=[TOOL_SEARCH_KYMA_DOC],
        must_not_call_tools=[TOOL_KYMA_QUERY],
        expected_goal=EXPECTED_BTP_MANAGER_RESPONSE,
        max_tool_calls=3,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    UI_CONTEXT_TEST_CASES,
    ids=[tc.name for tc in UI_CONTEXT_TEST_CASES],
)
@pytest.mark.asyncio
async def test_ui_context(react_agent, tool_tracker, goal_accuracy_metric, test_case: ReactAgentTestCase):
    """Verify UINavigationContext is used correctly by the agent."""
    result = await react_agent.ainvoke(
        query=test_case.query,
        chat_history=test_case.chat_history,
        ui_context=test_case.ui_context,
        callbacks=[tool_tracker],
    )

    # Basic assertions
    assert isinstance(result, str)
    assert len(result) > 0

    # Tool assertions
    assert_tool_invariants(test_case, tool_tracker)

    # Goal accuracy evaluation
    if test_case.expected_goal:
        sample = SingleTurnSample(
            user_input=test_case.query,
            response=result,
            reference=test_case.expected_goal,
        )
        score = await goal_accuracy_metric.single_turn_ascore(sample)
        if score < GOAL_ACCURACY_THRESHOLD:
            print(
                f"**Test case failed to meet expectation:**\n"
                f"--> Expected goal: {test_case.expected_goal}\n"
                f"--> Agent response: \n{result}"
            )
        assert score >= GOAL_ACCURACY_THRESHOLD, (
            f"Test case: {test_case.name}. Goal accuracy ({score:.2f}) is below threshold {GOAL_ACCURACY_THRESHOLD}"
        )


# ---------------------------------------------------------------------------
# 4. Multi-Turn Chat History
# ---------------------------------------------------------------------------


CHAT_HISTORY_TEST_CASES = [
    ReactAgentTestCase(
        name="Follow-up question resolves pronoun from history",
        query="What is wrong with it?",
        chat_history=[
            HumanMessage(content="What functions exist in namespace test-function-8?"),
            AIMessage(content="There is a function named func1 in namespace test-function-8."),
        ],
        ui_context=UINavigationContext(
            resource_kind="Function",
            resource_name="func1",
            namespace="test-function-8",
            resource_api_version="serverless.kyma-project.io/v1alpha2",
        ),
        must_call_tools=[TOOL_KYMA_QUERY],
        expected_goal="There is a syntax error in the JavaScript code. Date must be used instead of Dates.",
        max_tool_calls=6,
    ),
    ReactAgentTestCase(
        name="Empty history works without error",
        query="What is Kyma?",
        chat_history=[],
        min_response_length=50,
    ),
    ReactAgentTestCase(
        name="None history works without error",
        query="What is Kyma?",
        chat_history=None,
        min_response_length=50,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    CHAT_HISTORY_TEST_CASES,
    ids=[tc.name for tc in CHAT_HISTORY_TEST_CASES],
)
@pytest.mark.asyncio
async def test_chat_history(react_agent, tool_tracker, goal_accuracy_metric, test_case: ReactAgentTestCase):
    """Verify chat_history is passed correctly and the agent uses prior context."""
    result = await react_agent.ainvoke(
        query=test_case.query,
        chat_history=test_case.chat_history,
        ui_context=test_case.ui_context,
        callbacks=[tool_tracker],
    )

    # Basic assertions
    assert isinstance(result, str)
    assert len(result) >= test_case.min_response_length, f"Response too short ({len(result)} chars): {result[:200]}"

    # Tool assertions (if specified)
    if test_case.must_call_tools or test_case.must_not_call_tools:
        assert_tool_invariants(test_case, tool_tracker)

    # Goal accuracy (if expected_goal specified)
    if test_case.expected_goal:
        sample = SingleTurnSample(
            user_input=test_case.query,
            response=result,
            reference=test_case.expected_goal,
        )
        score = await goal_accuracy_metric.single_turn_ascore(sample)
        assert score >= GOAL_ACCURACY_THRESHOLD, (
            f"Test case: {test_case.name}. Goal accuracy ({score:.2f}) is below threshold {GOAL_ACCURACY_THRESHOLD}"
        )


# ---------------------------------------------------------------------------
# 5. Error Handling & Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_handling_k8s_failure(app_models, tool_tracker):
    """Verify graceful degradation when k8s_client raises an exception."""
    mock_client = Mock(spec_set=IK8sClient)
    mock_client.execute_get_api_request = AsyncMock(side_effect=Exception("connection refused"))
    agent = KymaReActAgent(models=app_models, k8s_client=mock_client)

    result = await agent.ainvoke(
        query="What is the status of function func1 in namespace test-function-8?",
        ui_context=UINavigationContext(
            resource_kind="Function",
            resource_name="func1",
            namespace="test-function-8",
            resource_api_version="serverless.kyma-project.io/v1alpha2",
        ),
        callbacks=[tool_tracker],
    )

    # Agent should return a string (not crash with unhandled exception)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_error_handling_very_long_query(react_agent):
    """Verify agent handles very long queries without crashing."""
    long_query = "What is wrong with my function? " * 200  # ~6400 chars

    result = await react_agent.ainvoke(query=long_query)

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_error_handling_none_callbacks(react_agent):
    """Verify agent works fine with callbacks=None."""
    result = await react_agent.ainvoke(
        query="What is Kyma?",
        callbacks=None,
    )

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# 6. Goal Accuracy with Live Cluster
# ---------------------------------------------------------------------------


GOAL_ACCURACY_TEST_CASES = [
    ReactAgentTestCase(
        name="Detect syntax error in Function via live cluster",
        query="What is wrong with function?",
        ui_context=UINavigationContext(
            resource_kind="Function",
            resource_name="func1",
            namespace="test-function-8",
            resource_api_version="serverless.kyma-project.io/v1alpha2",
        ),
        expected_goal="There is a syntax error in the JavaScript code. Date must be used instead of Dates.",
        must_call_tools=[TOOL_KYMA_QUERY],
        max_tool_calls=6,
    ),
    ReactAgentTestCase(
        name="General knowledge - BTP Operator",
        query="What are the BTP Operator features?",
        expected_goal=EXPECTED_BTP_MANAGER_RESPONSE,
        must_call_tools=[TOOL_SEARCH_KYMA_DOC],
        must_not_call_tools=[TOOL_KYMA_QUERY],
        max_tool_calls=3,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    GOAL_ACCURACY_TEST_CASES,
    ids=[tc.name for tc in GOAL_ACCURACY_TEST_CASES],
)
@pytest.mark.asyncio
async def test_goal_accuracy(react_agent, tool_tracker, goal_accuracy_metric, test_case: ReactAgentTestCase):
    """End-to-end goal accuracy test with real cluster (ragas SimpleCriteriaScore)."""
    result = await react_agent.ainvoke(
        query=test_case.query,
        chat_history=test_case.chat_history,
        ui_context=test_case.ui_context,
        callbacks=[tool_tracker],
    )

    # Basic assertions
    assert isinstance(result, str)
    assert len(result) > 0

    # Tool assertions
    assert_tool_invariants(test_case, tool_tracker)

    # Goal accuracy evaluation
    sample = SingleTurnSample(
        user_input=test_case.query,
        response=result,
        reference=test_case.expected_goal,
    )
    score = await goal_accuracy_metric.single_turn_ascore(sample)
    if score < GOAL_ACCURACY_THRESHOLD:
        print(
            f"**Test case failed to meet expectation:**\n"
            f"--> Test: {test_case.name}\n"
            f"--> Expected goal: {test_case.expected_goal}\n"
            f"--> Agent response: \n{result}\n"
            f"--> Tool calls: {tool_tracker.tool_names}"
        )

    assert score >= GOAL_ACCURACY_THRESHOLD, (
        f"Test case: {test_case.name}. Goal accuracy ({score:.2f}) is below threshold {GOAL_ACCURACY_THRESHOLD}"
    )


# ---------------------------------------------------------------------------
# 7. Callback Support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callbacks_receive_events(react_agent):
    """Verify custom callbacks are passed through and receive LLM events."""
    callback = Mock(spec=BaseCallbackHandler)
    # Make on_llm_start/on_llm_end not raise when called
    callback.on_llm_start = Mock()
    callback.on_llm_end = Mock()
    callback.on_tool_start = Mock()
    callback.on_tool_end = Mock()
    # Must set these attributes so LangChain doesn't skip the callback
    callback.raise_error = False
    callback.ignore_llm = False
    callback.ignore_agent = False
    callback.ignore_chain = False
    callback.ignore_retry = True
    callback.ignore_custom_event = True
    callback.ignore_chat_model = False

    await react_agent.ainvoke(
        query="What is Kyma?",
        callbacks=[callback],
    )

    # LLM should have been invoked at least once
    assert callback.on_llm_start.called or callback.on_tool_start.called, (
        "Callback should have received at least one LLM or tool event"
    )


@pytest.mark.asyncio
async def test_callbacks_none_works(react_agent):
    """Verify agent works with callbacks=None (no crash)."""
    result = await react_agent.ainvoke(
        query="What is Kyma?",
        callbacks=None,
    )
    assert isinstance(result, str)
    assert len(result) > 0
