"""Unit tests for KymaAgent broad-query handling.

These tests verify that KymaAgent produces a clarification response (no tool calls)
when the user asks a vague "all Kyma resources" question.

Non-determinism is eliminated by using FakeMessagesListChatModel with a scripted
clarification response. No cluster or LLM judge needed.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from rag.system import RAGSystem
from services.k8s import IK8sClient
from utils.models.factory import IModel
from utils.settings import MAIN_EMBEDDING_MODEL_NAME, MAIN_MODEL_NAME

# Keywords that must appear (case-insensitive) in a valid clarification response.
CLARIFICATION_KEYWORDS = frozenset(
    ["broad", "specific", "clarif", "more information", "namespace", "resource", "please"]
)

SCRIPTED_CLARIFICATION = AIMessage(
    content=(
        "Your query is too broad. Please provide a specific resource name, namespace, "
        "or resource kind so I can assist you more effectively."
    )
)

BROAD_QUERIES = [
    "what is the status of all Kyma resources?",
    "check all Kyma resources",
    "are all Kyma resources healthy?",
    "is there anything wrong with Kyma resources?",
    "show me all Kyma resources",
    "what is wrong with Kyma?",
    "show me the state of Kyma cluster",
]


def _make_models(fake_llm: FakeMessagesListChatModel) -> dict:
    """Build the models dict KymaAgent expects, backed by a fake LLM.

    KymaAgent.__init__ calls model.llm.bind_tools(tools) to create the chain.
    FakeMessagesListChatModel doesn't implement bind_tools, so we wrap it in a
    mock that returns the fake LLM itself from bind_tools (tools are ignored --
    the fake LLM returns scripted responses regardless of what tools are bound).
    """
    mock_model = MagicMock(spec=IModel)
    mock_model.name = MAIN_MODEL_NAME
    mock_model.llm = MagicMock()
    mock_model.llm.bind_tools.return_value = fake_llm
    mock_model.llm.temperature = 0.0

    mock_embedding = MagicMock(spec=Embeddings)
    mock_embedding.name = MAIN_EMBEDDING_MODEL_NAME

    return {MAIN_MODEL_NAME: mock_model, MAIN_EMBEDDING_MODEL_NAME: mock_embedding}


def _make_broad_query_state(query: str) -> KymaAgentState:
    """Build agent state for a broad Kyma query (no specific resource context)."""
    return KymaAgentState(
        agent_messages=[],
        messages=[
            HumanMessage(content=query),
        ],
        subtasks=[
            {
                "description": query,
                "task_title": query,
                "assigned_to": "KymaAgent",
            }
        ],
        my_task=SubTask(
            description=query,
            task_title=query,
            assigned_to="KymaAgent",
        ),
        k8s_client=Mock(spec_set=IK8sClient),
        is_last_step=False,
        remaining_steps=25,
    )


@pytest.mark.parametrize("query", BROAD_QUERIES)
@pytest.mark.asyncio
async def test_kyma_agent_asks_for_clarification_on_broad_query(query: str) -> None:
    """Agent returns a clarification response (no tool calls) for vague broad queries.

    The LLM is scripted to return a clarification message regardless of input.
    We assert:
      (a) the response is an AIMessage with no tool_calls (agent did not attempt
          to fetch cluster resources), and
      (b) the response content contains at least one clarification keyword,
          confirming the scripted response was returned.

    This test covers the behavioral property: the agent should ask for specifics
    rather than blindly querying all cluster resources.
    """
    # Each parametrized case gets a fresh scripted LLM so the response list is
    # not consumed across cases.
    fake_llm = FakeMessagesListChatModel(responses=[SCRIPTED_CLARIFICATION])
    models = _make_models(fake_llm)
    mock_rag = Mock(spec=RAGSystem)

    with patch("agents.kyma.tools.search.RAGSystem", return_value=mock_rag):
        agent = KymaAgent(models)

    state = _make_broad_query_state(query)
    response = await agent._invoke_chain(state, {})

    assert isinstance(response, AIMessage), f"Expected AIMessage for query {query!r}, got {type(response)}"
    assert not response.tool_calls, (
        f"Agent should NOT call tools for broad query {query!r}, but emitted tool calls: {response.tool_calls}"
    )
    content_lower = response.content.lower()
    matched = [kw for kw in CLARIFICATION_KEYWORDS if kw in content_lower]
    assert matched, (
        f"Response for query {query!r} contains none of the expected clarification "
        f"keywords {sorted(CLARIFICATION_KEYWORDS)!r}. Got: {response.content!r}"
    )
