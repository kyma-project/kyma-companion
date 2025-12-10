import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from integration.conftest import create_mock_state
from integration.test_utils import BaseTestCase


class TestCase(BaseTestCase):
    def __init__(self, name: str, messages: list, expected_answer: bool):
        super().__init__(name)
        self.messages = messages
        self.expected_answer = expected_answer


def create_test_cases():
    return [
        TestCase(
            "Should recognize positive feedback from user",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="your response is useful."),
            ],
            True,
        ),
        TestCase(
            "Should recognize gratitude as positive feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Pod', 'resource_api_version': 'v1', 'resource_name': 'test-pod', 'namespace': 'default'}"
                ),
                HumanMessage(content="Thanks, that helped!"),
            ],
            True,
        ),
        TestCase(
            "Should recognize confirmation that solution worked",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Deployment', 'resource_api_version': 'apps/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Perfect, exactly what I needed"),
            ],
            True,
        ),
        TestCase(
            "Should recognize enthusiastic positive feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Service', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Great explanation! This solved my problem."),
            ],
            True,
        ),
        TestCase(
            "Should recognize negative feedback about wrong response",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="this is wrong response."),
            ],
            True,
        ),
        TestCase(
            "Should recognize feedback that solution doesn't work",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'ConfigMap', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="This doesn't work for my use case."),
            ],
            True,
        ),
        TestCase(
            "Should recognize feedback about off-topic response",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Ingress', 'resource_api_version': 'networking.k8s.io/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="This is not what I asked for."),
            ],
            True,
        ),
        TestCase(
            "Should recognize feedback about incomplete solution",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'StatefulSet', 'resource_api_version': 'apps/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="The solution is incomplete and missing steps."),
            ],
            True,
        ),
        TestCase(
            "Should not treat request for more explanation as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'PersistentVolume', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Can you explain this better?"),
            ],
            False,
        ),
        TestCase(
            "Should not treat request for more details as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Job', 'resource_api_version': 'batch/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="I need more details about this approach."),
            ],
            False,
        ),
        TestCase(
            "Should not treat question about specific scenario as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'CronJob', 'resource_api_version': 'batch/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="What about high availability scenarios?"),
            ],
            False,
        ),
        TestCase(
            "Should recognize partial positive with info request as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Namespace', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(
                    content="This is helpful but I need more information about security aspects."
                ),
            ],
            True,
        ),
        TestCase(
            "Should not treat neutral response as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'RoleBinding', 'resource_api_version': 'rbac.authorization.k8s.io/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Alright."),
            ],
            False,
        ),
        TestCase(
            "Should recognize technical error feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'CustomResourceDefinition', 'resource_api_version': 'apiextensions.k8s.io/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="The YAML syntax is incorrect in your example."),
            ],
            True,
        ),
        TestCase(
            "Should not treat request for alternative approach as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'HorizontalPodAutoscaler', 'resource_api_version': 'autoscaling/v2', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(
                    content="Is there a different way to achieve this without using HPA?"
                ),
            ],
            False,
        ),
        TestCase(
            "Should not treat minimal acknowledgment as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'ServiceAccount', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Hmm, okay."),
            ],
            False,
        ),
        TestCase(
            "Should not treat brief confirmation as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'Role', 'resource_api_version': 'rbac.authorization.k8s.io/v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="I see."),
            ],
            False,
        ),
        TestCase(
            "Should not treat clarification request as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'ConfigMap', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Can you clarify more?"),
            ],
            False,
        ),
        TestCase(
            "Should not treat elaboration request as feedback",
            [
                SystemMessage(
                    content=""
                    "{'resource_kind': 'ConfigMap', 'resource_api_version': 'v1', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="Can you elaborate more?"),
            ],
            False,
        ),
        TestCase(
            "Should not treat format preference request as feedback",
            [
                SystemMessage(content=""),
                HumanMessage(content="give me a shorter explanation"),
            ],
            False,
        ),
    ]


@pytest.mark.parametrize("test_case", create_test_cases())
@pytest.mark.asyncio
async def test_invoke_feedback_node(
    test_case: TestCase,
    companion_graph,
):
    """
    Tests that the invoke_feedback_node feedback classification works as expected.
    """
    # Given: a conversation state with messages
    state = create_mock_state(test_case.messages)

    # When: the feedback node's invoke_feedback_node method is invoked
    actual_response = await companion_graph._invoke_feedback_node(state)
    assert actual_response.response == test_case.expected_answer, (
        f"{test_case.name}: Expected {test_case.expected_answer} "
        f"but got {actual_response.response}"
    )
