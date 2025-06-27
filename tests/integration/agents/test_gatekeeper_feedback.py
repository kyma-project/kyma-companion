import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common.constants import FEEDBACK
from integration.conftest import create_mock_state


@pytest.mark.parametrize(
    "test_description, messages, expected_answer",
    [  # Implicit Kubernetes/Kyma queries that should be forwarded
        (
            "user gives good feedback",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="your response is useful."),
            ],
            FEEDBACK,
        ),
        # Additional positive feedback variations
        (
            "user expresses gratitude",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Pod', 'resource_api_version': 'v1', 'resource_name': 'test-pod', 'namespace': 'default'}"
                ),
                HumanMessage(content="Thanks, that helped!"),
            ],
            FEEDBACK,
        ),
        (
            "user confirms solution worked",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Deployment', 'resource_api_version': 'apps/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Perfect, exactly what I needed"),
            ],
            FEEDBACK,
        ),
        (
            "user gives enthusiastic positive feedback",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Service', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Great explanation! This solved my problem."),
            ],
            FEEDBACK,
        ),
        (
            "user gives bad feedback",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="this is wrong response."),
            ],
            "forward",
        ),
        # Additional negative feedback variations
        (
            "user states solution doesn't work",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'ConfigMap', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="This doesn't work for my use case."),
            ],
            "forward",
        ),
        (
            "user states response is off-topic",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Ingress', 'resource_api_version': 'networking.k8s.io/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="This is not what I asked for."),
            ],
            "forward",
        ),
        (
            "user finds solution incomplete",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'StatefulSet', 'resource_api_version': 'apps/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="The solution is incomplete and missing steps."),
            ],
            "forward",
        ),
        # Neutral/clarifying feedback
        (
            "user requests more explanation",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'PersistentVolume', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Can you explain this better?"),
            ],
            "forward",
        ),
        (
            "user requests more details",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Job', 'resource_api_version': 'batch/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="I need more details about this approach."),
            ],
            "forward",
        ),
        (
            "user asks about specific scenario",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'CronJob', 'resource_api_version': 'batch/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="What about high availability scenarios?"),
            ],
            "forward",
        ),
        # Mixed feedback
        (
            "user gives partial positive with request for more info",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Namespace', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(
                    content="This is helpful but I need more information about security aspects."
                ),
            ],
            "forward",
        ),
        (
            "user gives neutral response",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'RoleBinding', 'resource_api_version': 'rbac.authorization.k8s.io/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Alright."),
            ],
            "forward",
        ),
        # Specific technical feedback
        (
            "user points out technical error",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'CustomResourceDefinition', 'resource_api_version': 'apiextensions.k8s.io/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="The YAML syntax is incorrect in your example."),
            ],
            "forward",
        ),
        (
            "user requests alternative approach",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'HorizontalPodAutoscaler', 'resource_api_version': 'autoscaling/v2', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(
                    content="Is there a different way to achieve this without using HPA?"
                ),
            ],
            "forward",
        ),
        # I am still confused
        (
            "user is still confused",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Secret', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="I'm still confused about this."),
            ],
            "forward",
        ),
        # Ambiguous feedback
        (
            "user gives minimal acknowledgment",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'ServiceAccount', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Hmm, okay."),
            ],
            "forward",
        ),
        (
            "user gives brief confirmation",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Role', 'resource_api_version': 'rbac.authorization.k8s.io/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="I see."),
            ],
            "forward",
        ),
    ],
)
@pytest.mark.asyncio
async def test_invoke_feedback_node(
    test_description,
    messages,
    expected_answer,
    companion_graph,
):
    """
    Tests that the invoke_feedback_node feedback classification works as expected.
    """
    # Given: a conversation state with messages
    state = create_mock_state(messages)

    # When: the feedback node's invoke_feedback_node method is invoked
    actual_response = await companion_graph._invoke_feedback_node(state)
    assert actual_response.response == expected_answer
