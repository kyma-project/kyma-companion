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


@pytest.fixture
def semantic_similarity_metric(evaluator_model):
    return GEval(
        name="Semantic Similarity",
        criteria=""
                 "Evaluate whether two answers are semantically similar or convey the same meaning.",
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.8,
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
        threshold=0.8,
    )


def create_mock_state(messages: Sequence[BaseMessage]) -> AgentState:
    """Create a mock langgraph state for tests."""
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
                    # tests if a general query is immediately answered by the planner
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content="What is the capital of Germany?"),
                ],
                '{"response": "Berlin"}',
                True,
        ),
        (
                # tests if a Kyma related query is assigned to the Kyma agent
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content="What is Kyma?"),
                ],
                '{"subtasks": [{"description": "What is Kyma?", "assigned_to": "KymaAgent"}]}',
                False,
        ),
        (
                # tests if a Kyma related query is assigned to the Kyma agent
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content="What is Kyma API Rule?"),
                ],
                '{"subtasks": [{"description": "What is Kyma API Rule?", "assigned_to": "KymaAgent"}]}',
                False,
        ),
        (
                # tests if a Kubernetes related query is assigned to the Kubernetes agent
                [
                    AIMessage(
                        content="The `nginx` container in the `nginx-5dbddc77dd-t5fm2` pod is experiencing a "
                                "`CrashLoopBackOff` state. The last termination reason was `StartError`"
                                " with the message indicating a failure to create the containerd task "
                                "due to a context cancellation."
                    ),
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content="why the pod is failing?"),
                ],
                "{'subtasks': [{'description': 'why the pod is failing?', 'assigned_to': 'KubernetesAgent'}]}",
                False,
        ),
        (
                # tests if a Kubernetes related query is assigned to the Kubernetes agent
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content="what is the status of my cluster?"),
                ],
                '{"subtasks": [{"description": "what is the status of my cluster?", "assigned_to": "KubernetesAgent"}]}',
                False,
        ),
        (
                # tests if a query related to Kyma and Kubernetes is divided into the correct subtasks for both agents
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content="What is Kubernetes? Explain Kyma function"),
                ],
                '{"subtasks": [{"description": "What is Kubernetes?", "assigned_to": "KubernetesAgent"},'
                '{"description": "Explain Kyma function", "assigned_to": "KymaAgent"}]}',
                False,
        ),
        (
                # tests if a query related to Kyma and Common is divided into the correct subtasks for both agents
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(
                        content="Create a hello world app and deploy it with Kyma?"
                    ),
                ],
                '{"subtasks": [{"description": "Create a hello world app", "assigned_to": "Common"},'
                '{"description": "deploy it with Kyma", "assigned_to": "KymaAgent"}]}',
                False,
        ),
        (
                # tests if a query related to Kyma and Common is divided into the correct subtasks for both agents
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(
                        content="Create a hello world app with python and deploy it with Kyma?"
                    ),
                ],
                '{"subtasks": [{"description": "Create a hello world app with python", "assigned_to": "Common"},'
                '{"description": "deploy it with Kyma", "assigned_to": "KymaAgent"}]}',
                False,
        ),
        (
                # tests if a complex query related to Kyma is divided correctly into two subtasks for the Kyma agent
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(
                        content="how to enable eventing module and create a subscription for my app?"
                    ),
                ],
                '{"subtasks": [{"description": "How to enable eventing module?", "assigned_to": "KymaAgent"},'
                '{"description": "How to create a subscription for my app?", "assigned_to": "KymaAgent"}]}',
                False,
        ),
    ],
)
def test_invoke_planner(
        messages,
        expected_answer,
        general_query,
        companion_graph,
        planner_correctness_metric,
        answer_relevancy_metric,
):
    """Tests the invoke_planner method of SupervisorAgent."""
    state = create_mock_state(messages)
    result = companion_graph.supervisor_agent._invoke_planner(state)

    test_case = LLMTestCase(
        input=messages[-1].content,
        actual_output=result.content,
        expected_output=expected_answer,
    )

    if not general_query:
        planner_correctness_metric.measure(test_case)

        print(f"Score: {planner_correctness_metric.score}")
        print(f"Reason: {planner_correctness_metric.reason}")

        # Parse the output to check if it is in valid JSON format
        companion_graph.plan_parser.parse(result.content)

        assert_test(test_case, [planner_correctness_metric])
    else:
        assert_test(test_case, [answer_relevancy_metric])


@pytest.mark.parametrize(
    "messages, expected_answer",
    [
        (
                # tests that the Finalizer node returns a general non-technical answer
                [
                    AIMessage(content="Berlin"),
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content="What is the capital of Germany?"),
                ],
                "The capital of Germany is Berlin.",
        ),
        # (
        #         # tests that the Finalizer node returns a kubernetes related answer
        #         [
        #             AIMessage(
        #                 content="The Pod is in error state because the Role grants the wrong access permissions to "
        #                         "the Pod. The permissions are `watch` when it should be `list`."
        #             ),
        #             SystemMessage(
        #                 content="The user query is related to: "
        #                         "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
        #             ),
        #             HumanMessage(content="Why is the pod in error state?"),
        #         ],
        #         "The Pod is in error state because the Role grants the wrong access permissions to "
        #         "the Pod. The permissions are `watch` when it should be `list`.",
        # ),
        # (
        #         # tests that the Finalizer node returns a kyma related answer
        #         [
        #             AIMessage(
        #                 content="Kyma is an open-source project designed natively on Kubernetes. It simplifies connecting "
        #                         "systems and extending applications with cloud-native technologies."
        #             ),
        #             SystemMessage(
        #                 content="The user query is related to: "
        #                         "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
        #             ),
        #             HumanMessage(content="What is Kyma?"),
        #         ],
        #         "Kyma is an opinionated set of Kubernetes-based modular building blocks, including all necessary "
        #         "capabilities to develop and run enterprise-grade cloud-native applications. It is the open path to "
        #         "the SAP ecosystem supporting business scenarios end-to-end.",
        # ),
        # (
        #         # tests that the Finalizer rejects a final response when not enough information for a Kubernetes related
        #         # answer is provided
        #         [
        #             AIMessage(
        #                 content="The sun is shining, the birds are chirping, and the flowers are blooming."
        #             ),
        #             SystemMessage(
        #                 content="The user query is related to: "
        #                         "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
        #             ),
        #             HumanMessage(content="Why is the pod failing?"),
        #         ],
        #         "I'm sorry, but I cannot answer your query at the moment.",
        # ),
        # (
                # tests that the Finalizer rejects a final response when not enough information for a Kyma related
                # answer is provided
                # [
                #     AIMessage(
                #         content="The sun is shining, the birds are chirping, and the flowers are blooming."
                #     ),
                #     SystemMessage(
                #         content="The user query is related to: "
                #                 "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                #     ),
                #     HumanMessage(content="What is Kyma?"),
                # ],
                # "I am sorry but I do not have enough information to answer your question.",
        # )
    ],
)
def test_invoke_finalizer(
        messages,
        expected_answer,
        companion_graph,
        semantic_similarity_metric
):
    """Tests the _generate_final_response method of SupervisorAgent"""
    state = create_mock_state(messages)

    result = companion_graph.supervisor_agent._generate_final_response(state)

    test_case = LLMTestCase(
        input=messages[-1].content,
        actual_output=result['messages'][0].content,
        expected_output=expected_answer,
    )

    assert_test(test_case, [semantic_similarity_metric])


@pytest.mark.parametrize(
    "messages, expected_answer",
    [
        (
                # tests that the Common node corretly answers a general non-technical query
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content="What is the capital of Germany?"),
                ],
                "Berlin",
        ),
        (
                # tests that the Common node correctly answers a general programming related query
                [
                    SystemMessage(
                        content="The user query is related to: "
                                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                    ),
                    HumanMessage(content='Write "Hello, World!" code in Python'),
                ],
                'Here is a simple "Hello, World!" program in Python: `print("Hello, World!")`',
        ),
    ],
)
def test_invoke_common_node(
        messages, expected_answer, companion_graph, answer_relevancy_metric
):
    """Tests the invoke_common_node method of CompanionGraph."""
    state = create_mock_state(messages)

    result = companion_graph._invoke_common_node(state, messages[-1].content)

    test_case = LLMTestCase(
        input=messages[-1].content,
        actual_output=result,
        expected_output=expected_answer,
    )

    assert_test(test_case, [answer_relevancy_metric])
