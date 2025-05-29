import pytest
from deepeval import assert_test
from deepeval.metrics import ConversationalGEval
from deepeval.test_case import ConversationalTestCase, LLMTestCase, LLMTestCaseParams
from langchain_core.messages import HumanMessage, SystemMessage

from integration.agents.fixtures.messages import (
    conversation_sample_6,
)
from integration.conftest import convert_dict_to_messages, create_mock_state


# Correctness metric for not general queries that needs planning
@pytest.fixture
def planner_correctness_metric(evaluator_model):
    return ConversationalGEval(
        name="Correctness",
        evaluation_steps=[
            "Determine whether the output is subtask(s) of the input and assigned to dedicated agent(s). ",
            "The output can contain a single subtask.",
            "Check if the output is in valid JSON format",
            "Verify that the JSON contains required keys: 'subtasks'",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.8,
        verbose_mode=True,
    )


@pytest.mark.parametrize(
    "messages, expected_answer, general_query",
    [
        (
            # tests if a Kyma related query is assigned to the Kyma agent
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is Kyma?"),
            ],
            '{"subtasks": [{"description": "What is Kyma?", "assigned_to": "KymaAgent" , "status" : "pending"}] }',
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
            '{"subtasks": [{ "description": "What is Kyma API Rule?", "assigned_to": "KymaAgent", "status" : "pending"}] }',
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
            '{"subtasks": [{"description": "what is the status of my cluster?", "assigned_to": "KubernetesAgent", "status" : "pending"}] }',
            False,
        ),
        (
            # tests if a query related to Kyma and Kubernetes is divided into the correct subtasks for both agents
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is Kubernetes and Explain Kyma function"),
            ],
            '{"subtasks": [{ "description": "What is Kubernetes",  "assigned_to": "KubernetesAgent","status" : "pending"},'
            '{"description": "Explain Kyma function",  "assigned_to": "KymaAgent","status" : "pending"}] }',
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
            '{ "subtasks": [{"description": "Create a hello world app", "assigned_to": "Common", "status" : "pending"},'
            '{"description": "deploy the app with Kyma", "assigned_to": "KymaAgent", "status" : "pending"}] }',
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
            '{ "subtasks": [{ "description": "Create a hello world app with python", "assigned_to": "Common", "status" : "pending"},'
            '{"description": "deploy it with Kyma", "assigned_to": "KymaAgent", "status" : "pending"}] }',
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
            '{ "subtasks": [{"description": "How to enable eventing module?", "assigned_to": "KymaAgent", "status" : "pending"},'
            '{"description": "How to create a subscription for my app?", "assigned_to": "KymaAgent", "status" :"pending"}]}',
            False,
        ),
        (
            # tests if a complex query related to Kyma , Kubernetes and some general query divided into three subtasks
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(
                    content="How to create a Python app that performs Discounted Cash Flow (DCF) calculations? How to create a Kyma function? How to create a k8s service for this function?"
                ),
            ],
            '{ "subtasks": [{"description": "How to create a Python app that performs Discounted Cash Flow (DCF) calculations?", "assigned_to": "Common", "status" : "pending"},'
            '{"description": "How to create a Kyma function?", "assigned_to": "KymaAgent", "status" :"pending"},'
            '{"description": "How to create a k8s service for this function?", "assigned_to": "KubernetesAgent", "status" :"pending"}] }',
            False,
        ),
    ],
)
@pytest.mark.asyncio
async def test_invoke_planner(
    messages,
    expected_answer,
    general_query,
    companion_graph,
    planner_correctness_metric,
    answer_relevancy_metric,
):
    """Tests the supervisor agent's invoke_planner method"""
    # Given: A conversation state with messages
    state = create_mock_state(messages)

    # When: The supervisor agent's planner is invoked
    result = await companion_graph.supervisor_agent._invoke_planner(state)

    # Then: We evaluate based on query type
    if not general_query:
        test_case = ConversationalTestCase(
            turns=[
                LLMTestCase(
                    input=str(messages),
                    actual_output=result.json(),
                    expected_output=expected_answer,
                )
            ]
        )

        assert_test(test_case, [planner_correctness_metric])
    else:
        # For general queries, check answer relevancy where planner directly answers
        # Then: We evaluate the response using deepeval metrics

        test_case = LLMTestCase(
            input=messages[-1].content,
            actual_output=result.json(),
            expected_output=expected_answer,
        )

        assert_test(test_case, [answer_relevancy_metric])


@pytest.fixture
def planner_conversation_history_metric(evaluator_model):
    return ConversationalGEval(
        name="Conversation History Correctness",
        evaluation_steps=[
            "Check the actual output that semantically matches expected output and answers the user query.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.8,
        async_mode=False,
        verbose_mode=True,
    )


@pytest.mark.parametrize(
    "messages, query, subtasks",
    [
        (
            # given the conversation, the planner knows that the user wants to expose the function
            # and assigns the task to the Kyma agent
            conversation_sample_6,
            "how to expose it?",
            [
                {
                    "description": "how to expose it?",
                    "assigned_to": "KymaAgent",
                    "status": "pending",
                    "result": None,
                }
            ],
        ),
        (
            # given the conversation, the planner knows that the user wants to convert the function to javascript
            # and assigns the task to the Kyma agent
            conversation_sample_6,
            "convert it to javascript",
            [
                {
                    "description": "convert the Kyma function that prints 'Hello World' from Python to JavaScript",
                    "assigned_to": "KymaAgent",
                    "status": "pending",
                    "result": None,
                }
            ],
        ),
    ],
)
@pytest.mark.asyncio
async def test_planner_with_conversation_history(
    messages,
    query,
    subtasks,
    companion_graph,
    planner_conversation_history_metric,
):
    """Tests if the planner properly considers conversation history when planning tasks."""
    # Given: A conversation state with messages
    all_messages = convert_dict_to_messages(messages)
    all_messages.append(HumanMessage(content=query))
    state = create_mock_state(all_messages)

    # When: The supervisor agent's planner is invoked
    result = await companion_graph.supervisor_agent._invoke_planner(state)

    # Then: We evaluate the response using deepeval metrics
    assert (
        result.subtasks is not None
    ), "Expected subtasks to be the same as the expected subtasks"

    # verify that the subtasks are the same as the expected subtasks
    test_case = ConversationalTestCase(
        turns=[
            LLMTestCase(
                input=str(all_messages),
                actual_output=str(result.subtasks),
                expected_output=str(subtasks),
            )
        ]
    )

    assert_test(test_case, [planner_conversation_history_metric])
