import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from integration.agents.test_common_node import create_mock_state


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
            '{"subtasks": null, "response": "Berlin"   }',
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
            '{"subtasks": [{"description": "What is Kyma?", "assigned_to": "KymaAgent" , "status" : "pending"}] , "response": null }',
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
            '{"subtasks": [{ "description": "What is Kyma API Rule?", "assigned_to": "KymaAgent", "status" : "pending"}] , "response": null}',
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
            "{'subtasks': [{  'description': 'why the pod is failing?', 'assigned_to': 'KubernetesAgent' ,'status' : 'pending'}] , 'response': null}",
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
            '{"subtasks": [{"description": "what is the status of my cluster?", "assigned_to": "KubernetesAgent", "status" : "pending"}] , "response": null}',
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
            '{"subtasks": [{ "description": "What is Kubernetes?", "assigned_to": "KubernetesAgent","status" : "pending"},'
            '{"description": "Explain Kyma function", "assigned_to": "KymaAgent","status" : "pending"}] , "response": null}',
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
            '{"description": "deploy the app with Kyma", "assigned_to": "KymaAgent", "status" : "pending"}] , "response": null}',
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
            '{"description": "deploy it with Kyma", "assigned_to": "KymaAgent", "status" : "pending"}] , "response": null}',
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
            '{"description": "How to create a subscription for my app?", "assigned_to": "KymaAgent", "status" :"pending"}] , "response": null}',
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
            '{"description": "How to create a k8s service for this function?", "assigned_to": "KubernetesAgent", "status" :"pending"}] , "response": null}',
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
    test_case = LLMTestCase(
        input=messages[-1].content,
        actual_output=result.json(),
        expected_output=expected_answer,
    )

    # Then: We evaluate based on query type
    if not general_query:
        # For Kyma or K8s queries, the generated plan is checked for correctness
        planner_correctness_metric.measure(test_case)

        print(f"Score: {planner_correctness_metric.score}")
        print(f"Reason: {planner_correctness_metric.reason}")

        assert_test(test_case, [planner_correctness_metric])
    else:
        # For general queries, check answer relevancy where planner directly answers
        assert_test(test_case, [answer_relevancy_metric])
