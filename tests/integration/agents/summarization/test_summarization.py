import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import (
    LLMTestCase,
    LLMTestCaseParams,
)
from langchain_core.messages import BaseMessage

from agents.summarization.prompts import (
    MESSAGES_SUMMARIZATION_INSTRUCTIONS,
)
from agents.summarization.summarization import MessageSummarizer
from integration.agents.fixtures.messages import (
    conversation_sample_1,
    conversation_sample_2,
    conversation_sample_3,
    conversation_sample_4,
)
from utils.settings import MAIN_MODEL_MINI_NAME, MAIN_MODEL_NAME


@pytest.fixture
def summarization_metric(evaluator_model):
    return GEval(
        name="Correctness",
        model=evaluator_model,
        threshold=0.5,
        # NOTE: you can only provide either criteria or evaluation_steps, and not both
        evaluation_steps=[
            "Determine whether the generated summary is factually correct based on the given conversation history.",
            "The summary must concisely represent the main issues, points or topics discussed in the given chat history.",
            "There must not be any duplicate points in the summary.",
            "No extra information is added to the summary which is not present in the previous summary or chat history.",
            f"The summary should follow the following given instructions:\n {MESSAGES_SUMMARIZATION_INSTRUCTIONS}",
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        async_mode=False,
        verbose_mode=True,
    )


@pytest.fixture
def summarization_model(app_models):
    return app_models[MAIN_MODEL_MINI_NAME]


@pytest.fixture
def tokenizer_info():
    return {
        "model_type": MAIN_MODEL_NAME,
        "token_lower_limit": 2000,
        "token_upper_limit": 3000,
    }


@pytest.mark.parametrize(
    "messages",
    [
        conversation_sample_1,
        conversation_sample_2,
        conversation_sample_3,
        conversation_sample_4,
    ],
)
@pytest.mark.asyncio
async def test_get_summary(
    summarization_metric,
    summarization_model,
    tokenizer_info,
    messages: list[BaseMessage],
):
    # given
    summarization = MessageSummarizer(
        model=summarization_model,
        tokenizer_model_name=tokenizer_info["model_type"],
        token_lower_limit=tokenizer_info["token_lower_limit"],
        token_upper_limit=tokenizer_info["token_upper_limit"],
    )

    # when
    generated_summary = await summarization.get_summary(messages, {})

    # then
    test_case = LLMTestCase(
        input=str(messages),
        actual_output=generated_summary,
    )

    assert_test(test_case, [summarization_metric])
