import pytest
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from agents.summarization.prompts import MESSAGES_SUMMARIZATION_PROMPT
from utils.models.factory import ModelType
from agents.summarization.summarization import Summarization
from deepeval.metrics import SummarizationMetric
from deepeval.test_case import LLMTestCase
from deepeval import evaluate
from integration.agents.summarization.fixtures.messages import conversation_sample_1, conversation_sample_2, conversation_sample_3, conversation_sample_4

@pytest.fixture
def summarization_metric(evaluator_model):
    return SummarizationMetric(
        threshold=0.7,
        model=evaluator_model,
        include_reason=True,
        assessment_questions=[
            f"Does the summary concisely represent the conversation as per the following prompt: \n\n {MESSAGES_SUMMARIZATION_PROMPT}?",
            "Does the summary enlist all the important points using bullets?",
            "There are no duplicate points in the summary.",
        ],
        async_mode=False,
        verbose_mode = True,
    )


@pytest.fixture
def summarization_model(app_models):
    return app_models[ModelType.GPT4O_MINI]

@pytest.fixture
def tokenizer_info():
    return {
        "model_type": ModelType.GPT4O,
        "token_lower_limit": 2000,
        "token_upper_limit": 3000
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
def test_get_summary(summarization_metric, summarization_model, tokenizer_info, messages: list[BaseMessage]):
    summarization = Summarization(
        model=summarization_model,
        tokenizer_model_type=tokenizer_info["model_type"],
        token_lower_limit=tokenizer_info["token_lower_limit"],
        token_upper_limit=tokenizer_info["token_upper_limit"],
    )

    actual_summary = summarization.get_summary(messages, {})

    test_case = LLMTestCase(input=str(messages), actual_output=actual_summary)
    results = evaluate(
        test_cases=[test_case],
        metrics=[summarization_metric],
        run_async=False,
    )
    # assert that all metrics passed
    assert all(
        result.success for result in results.test_results
    ), "Not all metrics passed"