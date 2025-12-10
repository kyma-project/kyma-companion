import json

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import HumanMessage, SystemMessage

from integration.agents.fixtures.messages import (
    conversation_sample_6,
)
from integration.conftest import convert_dict_to_messages, create_mock_state
from integration.test_utils import BaseTestCase


# Correctness metric for not general queries that needs planning
@pytest.fixture
def planner_correctness_metric(evaluator_model):
    def callback(threshold: float):
        return GEval(
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
            threshold=threshold,
            verbose_mode=True,
        )

    return callback


class PlannerTestCase(BaseTestCase):
    def __init__(
        self,
        name: str,
        messages: list,
        expected_answer: str,
        general_query: bool,
        threshold: float,
    ):
        super().__init__(name)
        self.messages = messages
        self.expected_answer = expected_answer
        self.general_query = general_query
        self.threshold = threshold


def create_planner_test_cases():
    return [
        PlannerTestCase(
            "Should create subtasks for both agents when listing everything in cluster",
            [
                SystemMessage(
                    content="{'resource_kind': 'Cluster', 'resource_scope': 'cluster'}"
                ),
                HumanMessage(content="list everything in my cluster"),
            ],
            '{"subtasks": [{"description": "list everything Kyma-related in my cluster", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "list everything Kubernetes-related in my cluster", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents when checking cluster resources",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'production'}"
                ),
                HumanMessage(content="check resources in the cluster"),
            ],
            '{"subtasks": [{"description": "check Kyma resources in the cluster", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "check Kubernetes resources in the cluster", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents for generic resource check",
            [
                SystemMessage(
                    content="{'resource_kind': 'Cluster', 'resource_scope': 'cluster'}"
                ),
                HumanMessage(content="check resources"),
            ],
            '{"subtasks": [{"description": "check Kyma resources", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "check Kubernetes resources", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents for complete resource overview",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'default'}"
                ),
                HumanMessage(content="give me a complete overview of my resources"),
            ],
            '{"subtasks": [{"description": "give me a complete overview of Kyma resources", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "give me a complete overview of Kubernetes resources", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents when requesting pods and serverless functions",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="show all pods and serverless functions"),
            ],
            '{"subtasks": [{"description": "show all serverless functions", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "show all pods", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should assign pod query to Kubernetes agent only",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="check all pods"),
            ],
            '{"subtasks": [{"description": "check all pods", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents when requesting services and API rules",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="list all services and API rules"),
            ],
            '{"subtasks": [{"description": "list all API rules", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "list all services", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents when asking what resources exist",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="what resources do I have in my cluster"),
            ],
            '{"subtasks": [{"description": "what Kyma resources do I have in my cluster", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "what Kubernetes resources do I have in my cluster", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents when showing everything deployed",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="show me everything deployed"),
            ],
            '{"subtasks": [{"description": "show me everything Kyma-related deployed", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "show me everything Kubernetes-related deployed", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents for workload and function status",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="get status of all workloads and functions"),
            ],
            '{"subtasks": [{"description": "get status of all functions", "assigned_to": "KymaAgent", "status": "pending"}, '
            '{"description": "get status of all workloads", "assigned_to": "KubernetesAgent", "status": "pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should answer general Kyma question directly without subtasks",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is Kyma?"),
            ],
            '{"subtasks": [{ "description": "What is Kyma?", "assigned_to": "KymaAgent", "status" : "pending"}] }',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should assign Kyma API Rule query to Kyma agent",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is Kyma API Rule?"),
            ],
            '{"subtasks": [{ "description": "What is Kyma API Rule?", "assigned_to": "KymaAgent", "status" : "pending"}] }',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should create subtasks for both agents for cluster status query",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="what is the status of my cluster?"),
            ],
            '{"subtasks": [{"description": "what is the status of my cluster?", "assigned_to": "KubernetesAgent", "status" : "pending"},{"description": "what is the status of my cluster?", "assigned_to": "KymaAgent", "status" : "pending"}] }',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should split Kubernetes and Kyma question into separate subtasks",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is Kubernetes and Explain Kyma function"),
            ],
            '{"subtasks": [{ "description": "What is Kubernetes",  "assigned_to": "KubernetesAgent","status" : "pending"},'
            '{"description": "Explain Kyma function",  "assigned_to": "KymaAgent","status" : "pending"}] }',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should split app creation and Kyma deployment into Common and Kyma subtasks",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(
                    content="Create a hello world app and deploy it with Kyma?"
                ),
            ],
            '{ "subtasks": [{"description": "Create a hello world app", "assigned_to": "Common", "status" : "pending"},'
            '{"description": "deploy the app with Kyma", "assigned_to": "KymaAgent", "status" : "pending"}] }',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should split Python app creation and Kyma deployment into Common and Kyma subtasks",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(
                    content="Create a hello world app with python and deploy it with Kyma?"
                ),
            ],
            '{ "subtasks": [{ "description": "Create a hello world app with python", "assigned_to": "Common", "status" : "pending"},'
            '{"description": "deploy it with Kyma", "assigned_to": "KymaAgent", "status" : "pending"}] }',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should split complex Kyma query into multiple Kyma agent subtasks",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(
                    content="how to enable eventing module and create a subscription for my app?"
                ),
            ],
            '{ "subtasks": [{"description": "How to enable eventing module?", "assigned_to": "KymaAgent", "status" : "pending"},'
            '{"description": "How to create a subscription for my app?", "assigned_to": "KymaAgent", "status" :"pending"}]}',
            False,
            0.8,
        ),
        PlannerTestCase(
            "Should split complex multi-agent query into Common, Kyma, and Kubernetes subtasks",
            [
                SystemMessage(
                    content=""
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
            0.8,
        ),
    ]


@pytest.mark.parametrize("test_case", create_planner_test_cases())
@pytest.mark.asyncio
async def test_invoke_planner(
    test_case: PlannerTestCase,
    companion_graph,
    planner_correctness_metric,
    answer_relevancy_metric,
):
    """Tests the supervisor agent's invoke_planner method"""
    # Given: A conversation state with messages
    state = create_mock_state(test_case.messages)

    # When: The supervisor agent's planner is invoked
    result = await companion_graph.supervisor_agent._invoke_planner(state)

    generated_plan = result.dict()
    # loop over subtasks and remove the task_title field
    for subtask in generated_plan.get("subtasks", []):
        subtask.pop("task_title", None)

    # Then: We evaluate based on query type
    if not test_case.general_query:
        llm_test_case = LLMTestCase(
            input=str(test_case.messages),
            actual_output=json.dumps(generated_plan),
            expected_output=test_case.expected_answer,
        )

        assert_test(
            llm_test_case,
            [planner_correctness_metric(test_case.threshold)],
            f"{test_case.name}: Plan should match expected subtask structure",
        )
    else:
        # For general queries, check answer relevancy where planner directly answers
        llm_test_case = LLMTestCase(
            input=test_case.messages[-1].content,
            actual_output=json.dumps(generated_plan),
            expected_output=test_case.expected_answer,
        )

        assert_test(
            llm_test_case,
            [answer_relevancy_metric],
            f"{test_case.name}: Answer should be relevant to query",
        )


@pytest.fixture
def planner_conversation_history_metric(evaluator_model):
    def callback(threshold: float):
        return GEval(
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
            threshold=threshold,
            verbose_mode=True,
        )

    return callback


class ConversationHistoryTestCase(BaseTestCase):
    def __init__(
        self,
        name: str,
        messages: list,
        query: str,
        expected_subtasks: list,
        threshold: float,
    ):
        super().__init__(name)
        self.messages = messages
        self.query = query
        self.expected_subtasks = expected_subtasks
        self.threshold = threshold


def create_conversation_history_test_cases():
    return [
        ConversationHistoryTestCase(
            "Should use conversation context to understand function exposure request",
            conversation_sample_6,
            "how to expose it?",
            [
                {
                    "description": "how to expose it?",
                    "task_title": "Fetching function exposure",
                    "assigned_to": "KymaAgent",
                    "status": "pending",
                }
            ],
            0.5,
        ),
        ConversationHistoryTestCase(
            "Should use conversation context to understand JavaScript conversion request",
            conversation_sample_6,
            "convert it to javascript",
            [
                {
                    "description": "convert it to javascript'",
                    "task_title": "Kyma function in JavaScript",
                    "assigned_to": "KymaAgent",
                    "status": "pending",
                }
            ],
            0.5,
        ),
    ]


@pytest.mark.parametrize("test_case", create_conversation_history_test_cases())
@pytest.mark.asyncio
async def test_planner_with_conversation_history(
    test_case: ConversationHistoryTestCase,
    companion_graph,
    planner_conversation_history_metric,
):
    """Tests if the planner properly considers conversation history when planning tasks."""
    # Given: A conversation state with messages
    all_messages = convert_dict_to_messages(test_case.messages)
    all_messages.append(HumanMessage(content=test_case.query))
    state = create_mock_state(all_messages)

    # When: The supervisor agent's planner is invoked
    result = await companion_graph.supervisor_agent._invoke_planner(state)
    # Then: We evaluate the response using deepeval metrics
    assert (
        result.subtasks is not None
    ), f"{test_case.name}: Expected subtasks to be the same as the expected subtasks"

    # verify that the subtasks are the same as the expected subtasks
    actual_subtasks = [subtask.model_dump(mode="json") for subtask in result.subtasks]
    llm_test_case = LLMTestCase(
        input=str(all_messages),
        actual_output=str(actual_subtasks),
        expected_output=str(test_case.expected_subtasks),
    )

    assert_test(
        llm_test_case,
        [planner_conversation_history_metric(test_case.threshold)],
        f"{test_case.name}: Subtasks should consider conversation history",
    )
