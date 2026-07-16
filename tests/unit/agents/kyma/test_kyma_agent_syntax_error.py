"""Unit tests for KymaAgent syntax error identification.

These tests verify that KymaAgent correctly processes a Kyma Function resource
containing a JavaScript syntax error (new Dates() instead of new Date()) and
communicates the fix to the user.

Non-determinism is eliminated by using FakeMessagesListChatModel, which returns
scripted responses instead of calling a live LLM. No cluster or judge needed.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from integration.agents.fixtures.serverless_function import SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR
from rag.system import RAGSystem
from services.k8s import IK8sClient
from utils.models.factory import IModel
from utils.settings import MAIN_EMBEDDING_MODEL_NAME, MAIN_MODEL_NAME

FUNCTION_URI = "/apis/serverless.kyma-project.io/v1alpha2/namespaces/test-function-8/functions/func1"

SCRIPTED_TOOL_CALL = AIMessage(
    content="",
    tool_calls=[
        {
            "id": "tool_call_id_1",
            "type": "tool_call",
            "name": "kyma_query_tool",
            "args": {"uri": FUNCTION_URI},
        }
    ],
)

SCRIPTED_ANSWER = AIMessage(
    content=(
        "The JavaScript code in the Function contains a syntax error: "
        "`new Dates()` should be `new Date()`. "
        "`Dates` is not a valid JavaScript constructor -- the correct built-in is `Date`."
    )
)


def _make_models(fake_llm: FakeMessagesListChatModel) -> dict:
    """Build the models dict KymaAgent expects, backed by a fake LLM.

    KymaAgent.__init__ calls model.llm.bind_tools(tools) to create the chain.
    FakeMessagesListChatModel doesn't implement bind_tools, so we wrap it in a
    mock that returns the fake LLM itself from bind_tools (tools are ignored --
    the fake LLM returns scripted responses regardless of what tools are bound).
    """
    mock_model = MagicMock(spec=IModel)
    mock_model.name = MAIN_MODEL_NAME
    # bind_tools must return something that supports pipe (|) with a prompt --
    # return the fake_llm itself, which is a Runnable.
    mock_model.llm = MagicMock()
    mock_model.llm.bind_tools.return_value = fake_llm
    mock_model.llm.temperature = 0.0

    mock_embedding = MagicMock(spec=Embeddings)
    mock_embedding.name = MAIN_EMBEDDING_MODEL_NAME

    return {MAIN_MODEL_NAME: mock_model, MAIN_EMBEDDING_MODEL_NAME: mock_embedding}


def _make_state(k8s_client: IK8sClient | None = None) -> KymaAgentState:
    """Build the initial agent state for the syntax-error scenario."""
    return KymaAgentState(
        agent_messages=[],
        messages=[
            SystemMessage(
                content=(
                    "{'resource_api_version': 'serverless.kyma-project.io/v1alpha2', "
                    "'resource_namespace': 'test-function-8', "
                    "'resource_kind': 'Function', "
                    "'resource_name': 'func1'}"
                )
            ),
            HumanMessage(content="What is wrong with function?"),
        ],
        subtasks=[
            {
                "description": "What is wrong with function?",
                "task_title": "What is wrong with function?",
                "assigned_to": "KymaAgent",
            }
        ],
        my_task=SubTask(
            description="What is wrong with function?",
            task_title="What is wrong with function?",
            assigned_to="KymaAgent",
        ),
        k8s_client=k8s_client,
        is_last_step=False,
        remaining_steps=25,
    )


def _make_state_with_preloaded_tool_response() -> KymaAgentState:
    """Build state with the tool response already injected.

    This skips the live cluster call -- the agent sees the Function YAML
    directly in the message history and only needs to reason about it.
    """
    return KymaAgentState(
        agent_messages=[],
        messages=[
            SystemMessage(
                content=(
                    "{'resource_api_version': 'serverless.kyma-project.io/v1alpha2', "
                    "'resource_namespace': 'test-function-8', "
                    "'resource_kind': 'Function', "
                    "'resource_name': 'func1'}"
                )
            ),
            HumanMessage(content="What is wrong with function?"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tool_call_id_1",
                        "type": "tool_call",
                        "name": "kyma_query_tool",
                        "args": {"uri": FUNCTION_URI},
                    }
                ],
            ),
            ToolMessage(
                content=SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
                name="kyma_query_tool",
                tool_call_id="tool_call_id_1",
            ),
        ],
        subtasks=[
            {
                "description": "What is wrong with function?",
                "task_title": "What is wrong with function?",
                "assigned_to": "KymaAgent",
            }
        ],
        my_task=SubTask(
            description="What is wrong with function?",
            task_title="What is wrong with function?",
            assigned_to="KymaAgent",
        ),
        k8s_client=Mock(spec_set=IK8sClient),
        is_last_step=False,
        remaining_steps=25,
    )


@pytest.mark.asyncio
async def test_kyma_agent_identifies_dates_syntax_error() -> None:
    """Agent correctly identifies Dates->Date syntax error from pre-loaded tool response.

    The LLM is scripted to return the answer directly (tool response already in state),
    so this test makes exactly one LLM call and asserts deterministic string content.
    """
    fake_llm = FakeMessagesListChatModel(responses=[SCRIPTED_ANSWER])
    models = _make_models(fake_llm)
    mock_rag = Mock(spec=RAGSystem)

    with patch("agents.kyma.tools.search.RAGSystem", return_value=mock_rag):
        agent = KymaAgent(models)

    state = _make_state_with_preloaded_tool_response()
    response = await agent._invoke_chain(state, {})

    assert isinstance(response, AIMessage), f"Expected AIMessage, got {type(response)}"
    content_lower = response.content.lower()
    assert "date" in content_lower, f"Expected 'Date' in response, got: {response.content!r}"
    assert "dates" not in content_lower.replace("date", ""), (
        f"Response should correct 'Dates' to 'Date', got: {response.content!r}"
    )


@pytest.mark.asyncio
async def test_kyma_agent_calls_kyma_query_tool_for_function_resource() -> None:
    """Agent issues a kyma_query_tool call when asked about a Function resource.

    The LLM is scripted to return a tool call first, verifying the agent
    routes to the correct tool before attempting to answer.
    """
    fake_llm = FakeMessagesListChatModel(responses=[SCRIPTED_TOOL_CALL])
    models = _make_models(fake_llm)
    mock_rag = Mock(spec=RAGSystem)

    with patch("agents.kyma.tools.search.RAGSystem", return_value=mock_rag):
        agent = KymaAgent(models)

    state = _make_state()
    response = await agent._invoke_chain(state, {})

    assert isinstance(response, AIMessage), f"Expected AIMessage, got {type(response)}"
    assert response.tool_calls, "Expected agent to emit a tool call"
    tool_name = response.tool_calls[0].get("name")
    assert tool_name == "kyma_query_tool", f"Expected kyma_query_tool call, got: {tool_name}"
