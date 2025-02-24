import pytest
from deepeval import evaluate
from deepeval.metrics import ConversationalGEval
from deepeval.test_case import ConversationalTestCase, LLMTestCase, LLMTestCaseParams
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
from utils.models.factory import ModelType


@pytest.fixture
def summarization_metric(evaluator_model):
    return ConversationalGEval(
        name="Correctness",
        model=evaluator_model,
        threshold=0.5,
        # criteria="Determine whether the generated summary is factually correct based on the given conversation history.",
        # NOTE: you can only provide either criteria or evaluation_steps, and not both
        evaluation_steps=[
            "Determine whether the generated summary is factually correct based on the given conversation history.",
            "The summary must concisely represent the main issues, points or topics discussed in the given chat history.",
            "There must not be any duplicate points in the summary.",
            "Penalize heavily if any extra information is added to the summary not present in the original conversation.",
            f"The summary should follow the following given instructions:\n {MESSAGES_SUMMARIZATION_INSTRUCTIONS}",
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        async_mode=False,
        verbose_mode=True,
    )


@pytest.fixture
def summarization_model(app_models):
    return app_models[ModelType.GPT4O_MINI]


@pytest.fixture
def tokenizer_info():
    return {
        "model_type": ModelType.GPT4O,
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
        tokenizer_model_type=tokenizer_info["model_type"],
        token_lower_limit=tokenizer_info["token_lower_limit"],
        token_upper_limit=tokenizer_info["token_upper_limit"],
    )

    # when
    generated_summary = await summarization.get_summary(messages, {})

    # then
    test_case = ConversationalTestCase(
        turns=[LLMTestCase(input=str(messages), actual_output=generated_summary)]
    )
    results = evaluate(
        test_cases=[test_case],
        metrics=[summarization_metric],
        run_async=False,
    )
    # assert that all metrics passed
    assert all(
        result.success for result in results.test_results
    ), "Not all metrics passed"
