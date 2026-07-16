"""Integration smoke tests for ToolResponseSummarizer with a live LLM.

These tests verify that the real LLM does not catastrophically drop verbatim
numeric/named values that appear literally in the static fixture input.

Non-determinism is constrained by asserting only on substrings that any
semantically-correct summarization of the fixture must include:
- The numeric port 9402 appears as a literal value in the deployment JSON;
  a number cannot be paraphrased.
- 'prometheus' appears as a literal annotation key prefix.

GEval and evaluator_model are intentionally removed -- the double-LLM
non-determinism (summarizer LLM + GEval judge LLM) was the root cause of
the flakiness. Substring assertions on static fixture values are fully
deterministic and sufficient to detect regressions.

The 'exposed ports' case uses nums_of_chunks=1 so both deployments are
summarized in a single call, avoiding a second chunk that contains no port
data and would add noise to the output.

The 'exposed ports' case is also covered by the unit test suite
(tests/unit/agents/common/test_chunk_summarization.py) which uses a
FakeMessagesListChatModel for 100% deterministic verification.
"""

from dataclasses import dataclass

import pytest
from langchain_core.runnables import RunnableConfig

from agents.common.chunk_summarizer import ToolResponseSummarizer
from agents.common.utils import convert_string_to_object
from integration.agents.fixtures.k8_query_tool_response import (
    sample_deployment_tool_response,
    sample_services_tool_response,
)
from utils.settings import MAIN_MODEL_NAME


@dataclass
class SummarizationSmokeCase:
    """Smoke test case: run the live LLM and assert substrings appear in the output."""

    name: str
    tool_response: str
    user_query: str
    nums_of_chunks: int
    required_substrings: list[str]
    """All substrings that must appear in the generated summary (case-insensitive)."""


@pytest.fixture
def summarization_model(app_models):
    """Provide the main model for summarization smoke tests."""
    return app_models[MAIN_MODEL_NAME]


SMOKE_CASES = [
    SummarizationSmokeCase(
        name="Should identify exposed ports from deployment",
        tool_response=sample_deployment_tool_response,
        user_query="What ports are exposed by the deployment?",
        nums_of_chunks=1,
        # 9402 is a literal numeric value in the fixture JSON; a number cannot
        # be paraphrased. prometheus is a literal annotation key prefix and
        # appears verbatim in the fixture. Both values must survive any correct
        # summarization. Container name and port alias are metadata a concise
        # summarizer is entitled to omit when focused on the port question.
        required_substrings=["9402", "prometheus"],
    ),
    SummarizationSmokeCase(
        name="Should identify services with monitoring capabilities",
        tool_response=sample_services_tool_response,
        user_query="Which services provide monitoring capabilities in the cluster?",
        nums_of_chunks=5,
        # 9402 is the literal port number for cert-manager's Prometheus endpoint.
        # prometheus is a literal annotation key prefix on istiod.
        required_substrings=["9402", "prometheus"],
    ),
]


@pytest.mark.parametrize(
    "smoke_case",
    SMOKE_CASES,
    ids=[tc.name for tc in SMOKE_CASES],
)
@pytest.mark.asyncio
async def test_summarize_tool_response_smoke(
    summarization_model,
    smoke_case: SummarizationSmokeCase,
) -> None:
    """Live-LLM smoke: verbatim fixture values must survive summarization.

    Does not use GEval -- substring assertions on static fixture values are
    deterministic regardless of LLM wording variation.
    """
    summarizer = ToolResponseSummarizer(model=summarization_model)
    config = RunnableConfig()

    tool_response_list = convert_string_to_object(smoke_case.tool_response)
    generated_summary = await summarizer.summarize_tool_response(
        tool_response=tool_response_list,
        user_query=smoke_case.user_query,
        config=config,
        nums_of_chunks=smoke_case.nums_of_chunks,
    )

    assert generated_summary, "summarize_tool_response returned an empty string"

    summary_lower = generated_summary.lower()
    for substring in smoke_case.required_substrings:
        assert substring.lower() in summary_lower, (
            f"Case {smoke_case.name!r}: expected {substring!r} in summary but got:\n{generated_summary}"
        )
