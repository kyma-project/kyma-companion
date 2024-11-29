import pytest
from langchain_core.messages import SystemMessage

from agents.common.constants import COMMON
from agents.common.state import SubTask
from agents.k8s.agent import K8S_AGENT
from agents.kyma.agent import KYMA_AGENT
from integration.agents.test_common_node import create_mock_state


@pytest.mark.parametrize(
    "messages, subtasks, expected_answer",
    [
        # Single task:
        # - Assigned K8sAgent is 'Next' agent
        # - Assigned KymaAgent is 'Next' agent
        # - Assigned Common is 'Next' agent
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(description="Task 1", assigned_to=K8S_AGENT, status="pending"),
            ],
            K8S_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(description="Task 1", assigned_to=KYMA_AGENT, status="pending"),
            ],
            KYMA_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(description="Task 1", assigned_to=COMMON, status="pending"),
            ],
            COMMON,
        ),
        # Multiple tasks, all still pending:
        # - First assigned K8sAgent is 'Next' agent
        # - First assigned KymaAgent is 'Next' agent
        # - First assigned Common is 'Next' agent
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(description="Task 1", assigned_to=K8S_AGENT, status="pending"),
                SubTask(description="Task 2", assigned_to=KYMA_AGENT, status="pending"),
            ],
            K8S_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(description="Task 1", assigned_to=KYMA_AGENT, status="pending"),
                SubTask(description="Task 2", assigned_to=K8S_AGENT, status="pending"),
            ],
            KYMA_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(description="Task 1", assigned_to=COMMON, status="pending"),
                SubTask(description="Task 2", assigned_to=KYMA_AGENT, status="pending"),
            ],
            COMMON,
        ),
        # Multiple tasks, the first one is completed:
        # - Second pending K8sAgent is 'Next' agent
        # - Second pending KymaAgent is 'Next' agent
        # - Second pending Common is 'Next' agent
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1", assigned_to=KYMA_AGENT, status="completed"
                ),
                SubTask(description="Task 2", assigned_to=K8S_AGENT, status="pending"),
            ],
            K8S_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1", assigned_to=K8S_AGENT, status="completed"
                ),
                SubTask(description="Task 2", assigned_to=KYMA_AGENT, status="pending"),
            ],
            KYMA_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1", assigned_to=KYMA_AGENT, status="completed"
                ),
                SubTask(description="Task 2", assigned_to=COMMON, status="pending"),
            ],
            COMMON,
        ),
    ],
)
def test_route(messages, subtasks, expected_answer, companion_graph):
    """Tests the router method of CompanionGraph."""
    # Given: A conversation state with messages and subtasks
    state = create_mock_state(messages, subtasks)

    # When: The supervisor agent's route method is invoked
    result = companion_graph.supervisor_agent._route(state)

    # Then: We verify the routing matches the expected output
    actual_output = result["next"]
    expected_output = expected_answer
    assert actual_output == expected_output, "Router did not return expected next step"
