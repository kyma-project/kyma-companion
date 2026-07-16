"""Integration smoke test: KymaAgent broad-query handling (real LLM).

Keeps exactly one broad-query case to catch prompt regressions where the real LLM
might start calling tools instead of asking for clarification.

Changes from the original 7-case test:
- Reduced to a single non-parametrized test (was 7 parametrized cases).
- Moved create_k8s_client() out of module-level TEST_CASES construction into
  the k8s_client fixture, eliminating cluster-auth-at-import-time failures
  during unit test collection.
- Removed the ragas judge (goal_accuracy_metric / evaluator_llm fixtures) -- it
  was already unused as a pass criterion in the prior iteration.
- Kept the judge-free structural assertion (no tool calls + non-empty response).

The other 6 broad-query variants are covered deterministically in
tests/unit/agents/kyma/test_kyma_agent_broad_query.py.
"""

import pytest
from langchain_core.messages import HumanMessage
from ragas.integrations.langgraph import convert_to_ragas_messages

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

# Single representative broad-query smoke case.
# The other 6 cases are covered deterministically in
# tests/unit/agents/kyma/test_kyma_agent_broad_query.py.
BROAD_QUERY_SMOKE = "what is the status of all Kyma resources?"


def _create_k8s_client() -> IK8sClient:
    """Build a live K8s client from test cluster settings.

    Called only from the k8s_client fixture -- NOT at module import time --
    so cluster auth is never attempted during unit test collection.
    """
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


@pytest.fixture
def k8s_client() -> IK8sClient:
    """Provide a live K8s client; constructed lazily so unit test collection never triggers this."""
    return _create_k8s_client()


@pytest.fixture
def kyma_agent(app_models) -> KymaAgent:
    """Provide a KymaAgent backed by live models."""
    return KymaAgent(app_models)


@pytest.mark.asyncio
async def test_kyma_agent_broad_query_asks_for_clarification(
    kyma_agent: KymaAgent,
    k8s_client: IK8sClient,
) -> None:
    """Real-LLM smoke test: agent must not call tools for a broad Kyma query.

    Structural assertion only (no ragas judge): the agent response must be
    non-empty and must contain no tool calls. This catches prompt regressions
    where a change to KYMA_AGENT_INSTRUCTIONS causes the real LLM to start
    fetching all cluster resources instead of asking for specifics.
    """
    state = KymaAgentState(
        agent_messages=[],
        messages=[HumanMessage(content=BROAD_QUERY_SMOKE)],
        subtasks=[
            {
                "description": BROAD_QUERY_SMOKE,
                "task_title": BROAD_QUERY_SMOKE,
                "assigned_to": "KymaAgent",
            }
        ],
        my_task=SubTask(
            description=BROAD_QUERY_SMOKE,
            task_title=BROAD_QUERY_SMOKE,
            assigned_to="KymaAgent",
        ),
        k8s_client=k8s_client,
        is_last_step=False,
        remaining_steps=AGENT_STEPS_NUMBER,
    )

    agent_response = await kyma_agent.agent_node().ainvoke(state)
    agent_messages = convert_to_ragas_messages(agent_response["agent_messages"])

    assert len(agent_messages) > 0, "Agent produced no messages for broad query smoke test"
    actual_output = agent_messages[-1].content
    assert actual_output, "Agent returned an empty response for broad query smoke test"

    tool_call_messages = [m for m in agent_response["agent_messages"] if hasattr(m, "tool_calls") and m.tool_calls]
    assert not tool_call_messages, (
        f"Agent should not call tools for broad query {BROAD_QUERY_SMOKE!r}, "
        f"but made tool calls: {[m.tool_calls for m in tool_call_messages]}"
    )
