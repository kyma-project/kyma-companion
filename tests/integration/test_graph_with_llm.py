import pytest
from deepeval import assert_test, evaluate
from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import HumanMessage

from agents.common.state import AgentState, UserInput
from agents.graph import KymaGraph
from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from integration.setup import custom_llm, model_mini, model
from utils.settings import REDIS_URL

memory = RedisSaver(async_connection=initialize_async_pool(url=REDIS_URL))
graph = KymaGraph(model_mini, memory)

# Define metrics
answer_relevancy_metric = AnswerRelevancyMetric(
    threshold=0.7, model=custom_llm, include_reason=True
)

# Correctness metric for not general queries that needs planning
correctness_metric = GEval(
    name="Correctness",
    criteria=""
    "Determine whether the output is subtask(s) of the input and assigned to dedicated agent(s). "
    "It is okay if the output contains one subtask."
    "Check if the output is in valid JSON format"
    "Verify that the JSON contains required keys: 'subtasks'",
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    model=custom_llm,
    threshold=0.7,
)


@pytest.mark.parametrize(
    "query, expected_answer, general_query",
    [
        (
            "What is the capital of Germany?",
            None,
            True,
        ),
        (
            "What is Kyma?",
            None,
            False,
        ),
        (
            "What is Kubernetes? Explain Kyma function",
            None,
            False,
        ),
        (
            "Create a hello world app and deploy it with Kyma? Explain the steps.",
            None,
            False,
        ),
        (
            "Create a hello world app with python and deploy it with Kyma? Explain the steps.",
            None,
            False,
        ),
    ],
)
def test_planner(query, expected_answer, general_query):
    # Generate actual output using LangChain
    user_input = UserInput(
        query=query,
        resource_kind=None,
        resource_api_version=None,
        resource_name=None,
        namespace=None,
    )

    state = AgentState(
        input=user_input,
        messages=[HumanMessage(content=query)],
        next="",
        subtasks=[],
        final_response="",
        error=None,
    )

    result = graph._invoke_planner(state)

    if not general_query:
        test_case = LLMTestCase(input=query, actual_output=result.content)

        correctness_metric.measure(test_case)

        print(f"Score: {correctness_metric.score}")
        print(f"Reason: {correctness_metric.reason}")
        # assert correctness_metric.score >= 0.7, correctness_metric.reason

        # TODO: validate the result.content to follow Plan schema
        plan = graph.plan_parser.parse(result.content)

        assert_test(test_case, [correctness_metric])
    else:
        test_case = LLMTestCase(input=query, actual_output=result.content)
        answer_relevancy_metric.measure(test_case)
        print(f"Score: {answer_relevancy_metric.score}")
        print(f"Reason: {answer_relevancy_metric.reason}")
        # assert answer_relevancy_metric.score >= 0.7, answer_relevancy_metric.reason

        assert_test(test_case, [answer_relevancy_metric])


@pytest.mark.parametrize(
    "query, expected_answer",
    [
        (
            "What is the capital of Germany?",
            None,
        ),
        (
            "What is Kyma?",
            None,
        ),
    ],
)
def test_common_node(query, expected_answer):
    # Generate actual output using LangChain
    user_input = UserInput(
        query=query,
        resource_kind=None,
        resource_api_version=None,
        resource_name=None,
        namespace=None,
    )

    state = AgentState(
        input=user_input,
        messages=[HumanMessage(content=query)],
        next="",
        subtasks=[],
        final_response="",
        error=None,
    )

    result = graph._invoke_common_node(state, query)
    test_case = LLMTestCase(input=query, actual_output=result)
    answer_relevancy_metric.measure(test_case)
    print(f"Score: {answer_relevancy_metric.score}")
    print(f"Reason: {answer_relevancy_metric.reason}")
    # assert answer_relevancy_metric.score >= 0.7, answer_relevancy_metric.reason
    assert_test(test_case, [answer_relevancy_metric])
