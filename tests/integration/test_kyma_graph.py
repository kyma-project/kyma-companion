from collections.abc import Sequence

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from agents.common.state import AgentState, UserInput


@pytest.fixture
def answer_relevancy_metric(evaluator_model):
    return AnswerRelevancyMetric(
        threshold=0.6, model=evaluator_model, include_reason=True
    )


# Correctness metric for not general queries that needs planning
@pytest.fixture
def planner_correctness_metric(evaluator_model):
    return GEval(
        name="Correctness",
        criteria=""
        "Determine whether the output is subtask(s) of the input and assigned to dedicated agent(s). "
        "It is okay if the output contains one subtask."
        "Check if the output is in valid JSON format"
        "Verify that the JSON contains required keys: 'subtasks'",
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.85,
    )


def create_state(messages: Sequence[BaseMessage]) -> AgentState:
    user_input = UserInput(
        query=messages[-1].content,
        resource_kind=None,
        resource_api_version=None,
        resource_name=None,
        namespace=None,
    )

    return AgentState(
        input=user_input,
        messages=messages,
        next="",
        subtasks=[],
        final_response="",
        error=None,
    )


@pytest.mark.parametrize(
    "messages, expected_answer, general_query",
    [
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is the capital of Germany?"),
            ],
            '{"response": "What is the capital of Germany?"}',
            True,
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="Write snake game in javascript"),
            ],
            '{"response": "Write snake game in javascript"}',
            True,
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is Kyma?"),
            ],
            '{"subtasks": [{"description": "What is Kyma?", "assigned_to": "KymaAgent"}]}',
            False,
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is Kyma API Rule?"),
            ],
            '{"subtasks": [{"description": "What is Kyma API Rule?", "assigned_to": "KymaAgent"}]}',
            False,
        ),
        (
            [
                AIMessage(
                    content="The `nginx` container in the `nginx-5dbddc77dd-t5fm2` pod is experiencing a `CrashLoopBackOff` state. The last termination reason was `StartError` with the message indicating a failure to create the containerd task due to a context cancellation."
                ),
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="why the pod is failing?"),
            ],
            "{'subtasks': [{'description': 'why the pod is failing?', 'assigned_to': 'KubernetesAgent'}]}",
            False,
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="what is the status of my cluster?"),
            ],
            '{"subtasks": [{"description": "what is the status of my cluster?", "assigned_to": "KubernetesAgent"}]}',
            False,
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is Kubernetes? Explain Kyma function"),
            ],
            '{"subtasks": [{"description": "What is Kubernetes?", "assigned_to": "KubernetesAgent"},{"description": "Explain Kyma function", "assigned_to": "KymaAgent"}]}',
            False,
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(
                    content="Create a hello world app and deploy it with Kyma?"
                ),
            ],
            '{"subtasks": [{"description": "Create a hello world app", "assigned_to": "Common"},{"description": "deploy it with Kyma", "assigned_to": "KymaAgent"}]}',
            False,
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(
                    content="Create a hello world app with python and deploy it with Kyma?"
                ),
            ],
            '{"subtasks": [{"description": "Create a hello world app with python", "assigned_to": "Common"},{"description": "deploy it with Kyma", "assigned_to": "KymaAgent"}]}',
            False,
        ),
    ],
)
def test_planner(
    messages,
    expected_answer,
    general_query,
    kyma_graph,
    planner_correctness_metric,
    answer_relevancy_metric,
):
    state = create_state(messages)
    result = kyma_graph._invoke_planner(state)

    test_case = LLMTestCase(
        input=messages[-1].content,
        actual_output=result.content,
        expected_output=expected_answer,
    )

    if not general_query:
        planner_correctness_metric.measure(test_case)

        print(f"Score: {planner_correctness_metric.score}")
        print(f"Reason: {planner_correctness_metric.reason}")

        # TODO: validate the result.content to follow Plan schema
        plan = kyma_graph.plan_parser.parse(result.content)
        # assert (
        #     planner_correctness_metric.score >= planner_correctness_metric.threshold
        # ), planner_correctness_metric.reason

        assert_test(test_case, [planner_correctness_metric])
    else:
        assert_test(test_case, [answer_relevancy_metric])


@pytest.mark.parametrize(
    "messages, expected_answer",
    [
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is the capital of Germany?"),
            ],
            "Berlin",
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content='Write "Hello, World!" code in Python'),
            ],
            'Here is a simple "Hello, World!" program in Python: `print("Hello, World!")`',
        ),
    ],
)
def test_common_node(messages, expected_answer, kyma_graph, answer_relevancy_metric):
    # Generate actual output using LangChain
    state = create_state(messages)

    result = kyma_graph._invoke_common_node(state, messages[-1].content)
    test_case = LLMTestCase(input=messages[-1].content, actual_output=result)
    assert_test(test_case, [answer_relevancy_metric])
