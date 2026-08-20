from dataclasses import dataclass, field

import pytest
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from agents.common.conversation_summarizer import ConversationSummarizer
from utils.settings import MAIN_MODEL_NAME


@pytest.fixture
def summarization_model(app_models):
    return app_models[MAIN_MODEL_NAME]


@pytest.fixture
def conversation_summary_metric(evaluator_model):
    return GEval(
        name="Conversation Summary Quality",
        model=evaluator_model,
        threshold=0.6,
        evaluation_steps=[
            "Determine whether the generated summary preserves the key facts listed in the expected summary.",
            "Verify that Kubernetes/Kyma resources mentioned (kinds, names, namespaces) are retained.",
            "Verify that the user's goals/problems and any root causes or fixes are retained.",
            "Do not penalize the summary for being concise or for omitting small talk.",
            "Do not penalize additional correct details not present in the expected summary.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        async_mode=False,
        verbose_mode=True,
    )


@dataclass
class ConversationSummaryTestCase:
    """Test case for conversation history summarization."""

    name: str
    messages: list[BaseMessage]
    expected_summary: str
    must_include: list[str] = field(default_factory=list)


def _kyma_troubleshooting_history() -> list[BaseMessage]:
    return [
        HumanMessage(content="My Kyma Function 'order-processor' in namespace 'shop' is not starting. Can you help?"),
        AIMessage(
            content=(
                "I inspected the Function 'order-processor' in namespace 'shop'. Its pod is in "
                "CrashLoopBackOff. The container logs show 'MODULE_NOT_FOUND: axios', so a runtime "
                "dependency is missing from the Function's dependencies."
            )
        ),
        HumanMessage(content="How do I fix the missing dependency?"),
        AIMessage(
            content=(
                "Add 'axios' to the Function's package.json dependencies via the spec.source dependencies "
                "field, then redeploy. After that the build job should succeed and the pod should reach "
                "Running state."
            )
        ),
        HumanMessage(content="I added axios but now I get an APIRule 503 error on host 'orders.example.com'."),
        AIMessage(
            content=(
                "The APIRule 'order-processor-api' points to service 'order-processor' on port 80, but the "
                "Function service exposes port 8080. Update the APIRule spec.service.port to 8080 to resolve "
                "the 503 on host 'orders.example.com'."
            )
        ),
    ]


TEST_CASES = [
    ConversationSummaryTestCase(
        name="Kyma Function troubleshooting session",
        messages=_kyma_troubleshooting_history(),
        expected_summary=(
            "The user is troubleshooting the Kyma Function 'order-processor' in namespace 'shop'. "
            "It was in CrashLoopBackOff because the 'axios' dependency was missing; the fix was to add "
            "'axios' to the Function dependencies and redeploy. Afterwards an APIRule 'order-processor-api' "
            "returned a 503 on host 'orders.example.com' because it targeted port 80 while the service "
            "exposes port 8080; the fix is to update the APIRule port to 8080."
        ),
        must_include=["order-processor", "shop"],
    ),
]


@pytest.mark.parametrize(
    "test_case",
    TEST_CASES,
    ids=[tc.name for tc in TEST_CASES],
)
@pytest.mark.asyncio
async def test_summarize_conversation_integration(
    conversation_summary_metric,
    summarization_model,
    test_case: ConversationSummaryTestCase,
):
    summarizer = ConversationSummarizer(model=summarization_model)

    generated_summary = await summarizer.summarize(test_case.messages, config=None)

    # Deterministic sanity checks: critical identifiers must survive summarization.
    for token in test_case.must_include:
        assert token in generated_summary, f"summary is missing required token '{token}'"

    llm_test_case = LLMTestCase(
        input=f"Expected Summary: {test_case.expected_summary}",
        actual_output=generated_summary,
    )
    await conversation_summary_metric.a_measure(llm_test_case)
    assert conversation_summary_metric.is_successful(), conversation_summary_metric.reason


def _make_pairs(num_pairs: int, filler: str) -> list[BaseMessage]:
    history: list[BaseMessage] = []
    for i in range(num_pairs):
        history.append(HumanMessage(content=f"{filler} question {i}"))
        history.append(AIMessage(content=f"{filler} answer {i}"))
    return history


@pytest.mark.asyncio
async def test_prepare_chat_history_below_limit_is_untouched(summarization_model, monkeypatch):
    """Short histories must be passed through verbatim (no LLM call)."""
    import agents.kyma.react_agent as mod

    monkeypatch.setattr(mod, "CHAT_HISTORY_TOKEN_LIMIT", 100_000)
    agent = mod.KymaReActAgent.__new__(mod.KymaReActAgent)
    agent._conversation_summarizer = ConversationSummarizer(model=summarization_model)

    history = _kyma_troubleshooting_history()
    result = await agent._prepare_chat_history(history, config=None)
    assert result == history


@pytest.mark.asyncio
async def test_prepare_chat_history_above_limit_summarizes_and_keeps_recent(summarization_model, monkeypatch):
    """Long histories are compressed: 1 summary SystemMessage + last N verbatim."""
    import agents.kyma.react_agent as mod

    monkeypatch.setattr(mod, "CHAT_HISTORY_TOKEN_LIMIT", 1)
    monkeypatch.setattr(mod, "CHAT_HISTORY_KEEP_MESSAGES", 4)
    agent = mod.KymaReActAgent.__new__(mod.KymaReActAgent)
    agent._conversation_summarizer = ConversationSummarizer(model=summarization_model)

    # 6 older filler pairs (12 msgs) + the 6-message kyma session tail we want kept.
    older = _make_pairs(6, "unrelated small talk")
    tail = _kyma_troubleshooting_history()
    history = [*older, *tail]

    result = await agent._prepare_chat_history(history, config=None)

    keep = 4
    assert isinstance(result[0], SystemMessage)
    assert str(result[0].content).startswith("Summary of earlier conversation:")
    assert result[1:] == history[-keep:]
    assert len(result) == 1 + keep
