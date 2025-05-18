from typing import Any

import pytest
from deepeval import evaluate
from deepeval.metrics import ConversationalGEval
from deepeval.test_case import ConversationalTestCase, LLMTestCase, LLMTestCaseParams
from langchain_core.runnables import RunnableConfig

from agents.common.chunk_summarizer import ToolResponseSummarizer
from utils.models.factory import ModelType

# Sample test data
tool_response_sample_1 = [
    {
        "content": "The weather in New York is sunny today with temperatures around 75°F."
    },
    {"content": "There's a 10% chance of rain in the evening."},
    {"content": "Tomorrow will be partly cloudy with a high of 78°F."},
]

tool_response_sample_2 = [
    {"content": "The stock market closed with NASDAQ up by 2.3% today."},
    {"content": "S&P 500 gained 1.8% reaching an all-time high."},
    {"content": "Tech stocks performed particularly well with Apple gaining 3.2%."},
    {
        "content": "Financial analysts predict continued growth through the next quarter."
    },
]

tool_response_sample_3 = [
    {"content": "Python 3.11 offers significant performance improvements over 3.10."},
    {
        "content": "New features include better error messages and enhanced typing capabilities."
    },
    {
        "content": "The update focuses on speed with some benchmarks showing up to 60% faster execution."
    },
    {
        "content": "Installation is recommended through official Python website or package managers."
    },
    {"content": "Most third-party libraries are now compatible with the new version."},
]

user_query_samples = [
    "What's the weather like in New York?",
    "How did the stock market perform today?",
    "Tell me about the latest Python version",
]

expected_summaries = [
    "The weather in New York is currently sunny with temperatures around 75°F. There is a 10% chance of rain in the evening. Tomorrow will be partly cloudy with a high of 78°F.",
    "The stock market closed positively today with NASDAQ up 2.3% and S&P 500 gaining 1.8%, reaching an all-time high. Tech stocks performed well, with Apple gaining 3.2%. Financial analysts predict continued growth in the next quarter.",
    "Python 3.11 offers significant performance improvements over version 3.10, with some benchmarks showing up to 60% faster execution. It features better error messages and enhanced typing capabilities. The update is available through the official Python website or package managers, and most third-party libraries are now compatible.",
]


@pytest.fixture
def tool_response_summarization_metric(evaluator_model):
    return ConversationalGEval(
        name="Tool Response Summarization Quality",
        model=evaluator_model,
        threshold=0.5,
        evaluation_steps=[
            "Determine whether the generated summary accurately represents all the information in the expected summary.",
            "Check if the summary is concise while preserving all important details",
            "Verify that the summary is relevant to the user's original query.",
            "Ensure that the summary does not contain any information not present in the expected summary.",
            "Evaluate whether the summary maintains proper flow and readability when joining multiple chunk summaries.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        async_mode=False,
        verbose_mode=True,
    )


@pytest.fixture
def summarization_model(app_models):
    return app_models[ModelType.GPT4O_MINI]


@pytest.mark.parametrize(
    "tool_response, user_query, nums_of_chunks, expected_summary",
    [
        (tool_response_sample_1, user_query_samples[0], 2, expected_summaries[0]),
        (tool_response_sample_2, user_query_samples[1], 2, expected_summaries[1]),
        (tool_response_sample_3, user_query_samples[2], 3, expected_summaries[2]),
    ],
)
@pytest.mark.asyncio
async def test_summarize_tool_response_integration(
    tool_response_summarization_metric,
    summarization_model,
    tool_response: list[Any],
    user_query: str,
    nums_of_chunks: int,
    expected_summary: str,
):
    summarizer = ToolResponseSummarizer(model=summarization_model)

    config = RunnableConfig()

    generated_summary = await summarizer.summarize_tool_response(
        tool_response=tool_response,
        user_query=user_query,
        config=config,
        nums_of_chunks=nums_of_chunks,
    )

    test_case = ConversationalTestCase(
        turns=[
            LLMTestCase(
                input=f"User Query: {user_query}\nExpected Summary: {expected_summary}",
                actual_output=generated_summary,
            )
        ]
    )
    results = evaluate(
        test_cases=[test_case],
        metrics=[tool_response_summarization_metric],
        run_async=False,
    )

    # Assert that all metrics passed
    assert all(
        result.success for result in results.test_results
    ), "Not all metrics passed"
