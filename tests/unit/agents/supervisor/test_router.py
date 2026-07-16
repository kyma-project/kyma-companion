from unittest.mock import MagicMock

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.messages import SystemMessage

from agents.common.constants import COMMON
from agents.common.state import SubTask
from agents.k8s.agent import K8S_AGENT
from agents.kyma.agent import KYMA_AGENT
from agents.supervisor.agent import FINALIZER, SupervisorAgent
from agents.supervisor.state import SupervisorState
from utils.models.factory import IModel
from utils.settings import (
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
    MAIN_MODEL_NAME,
)


@pytest.fixture
def supervisor_agent() -> SupervisorAgent:
    """Create a SupervisorAgent with mocked models for unit testing."""
    mock_models = {
        MAIN_MODEL_MINI_NAME: MagicMock(spec=IModel),
        MAIN_MODEL_NAME: MagicMock(spec=IModel),
        MAIN_EMBEDDING_MODEL_NAME: MagicMock(spec=Embeddings),
    }
    return SupervisorAgent(models=mock_models, members=[K8S_AGENT, KYMA_AGENT, COMMON, FINALIZER])


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
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=K8S_AGENT,
                    status="pending",
                ),
            ],
            K8S_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=KYMA_AGENT,
                    status="pending",
                ),
            ],
            KYMA_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=COMMON,
                    status="pending",
                ),
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
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=K8S_AGENT,
                    status="pending",
                ),
                SubTask(
                    description="Task 2",
                    task_title="Task 2",
                    assigned_to=KYMA_AGENT,
                    status="pending",
                ),
            ],
            K8S_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=KYMA_AGENT,
                    status="pending",
                ),
                SubTask(
                    description="Task 2",
                    task_title="Task 2",
                    assigned_to=K8S_AGENT,
                    status="pending",
                ),
            ],
            KYMA_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=COMMON,
                    status="pending",
                ),
                SubTask(
                    description="Task 2",
                    task_title="Task 2",
                    assigned_to=KYMA_AGENT,
                    status="pending",
                ),
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
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=KYMA_AGENT,
                    status="completed",
                ),
                SubTask(
                    description="Task 2",
                    task_title="Task 2",
                    assigned_to=K8S_AGENT,
                    status="pending",
                ),
            ],
            K8S_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=K8S_AGENT,
                    status="completed",
                ),
                SubTask(
                    description="Task 2",
                    task_title="Task 2",
                    assigned_to=KYMA_AGENT,
                    status="pending",
                ),
            ],
            KYMA_AGENT,
        ),
        (
            [
                SystemMessage(
                    content="""
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=KYMA_AGENT,
                    status="completed",
                ),
                SubTask(
                    description="Task 2",
                    task_title="Task 2",
                    assigned_to=COMMON,
                    status="pending",
                ),
            ],
            COMMON,
        ),
        # All subtasks completed: Finalizer is 'Next' agent
        (
            [
                SystemMessage(
                    content="""
                {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                )
            ],
            [
                SubTask(
                    description="Task 1",
                    task_title="Task 1",
                    assigned_to=K8S_AGENT,
                    status="completed",
                ),
                SubTask(
                    description="Task 2",
                    task_title="Task 2",
                    assigned_to=KYMA_AGENT,
                    status="completed",
                ),
            ],
            FINALIZER,
        ),
    ],
    ids=[
        "single_k8s_pending",
        "single_kyma_pending",
        "single_common_pending",
        "multi_all_pending_first_k8s",
        "multi_all_pending_first_kyma",
        "multi_all_pending_first_common",
        "multi_first_completed_k8s_next",
        "multi_first_completed_kyma_next",
        "multi_first_completed_common_next",
        "all_completed_finalizer",
    ],
)
def test_route(messages, subtasks, expected_answer, supervisor_agent):
    """Tests the _route method of SupervisorAgent."""
    # Given: A supervisor state with messages and subtasks
    state = SupervisorState(messages=messages, subtasks=subtasks)

    # When: The supervisor agent's _route method is invoked
    result = supervisor_agent._route(state)

    # Then: We verify the routing matches the expected output
    assert result["next"] == expected_answer, "Router did not return expected next step"
