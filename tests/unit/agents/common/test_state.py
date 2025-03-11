from unittest.mock import Mock

import pytest
from langchain_core.messages import (
    AIMessage,
    SystemMessage,
)

from agents.common.state import (
    BaseAgentState,
    CompanionState,
    SubTask,
    SubTaskStatus,
    UserInput,
)
from services.k8s import IK8sClient


class TestSubTask:
    # Test data for SubTask
    @pytest.mark.parametrize(
        "description, task_title,assigned_to, status, result, expected_status",
        [
            (
                "Task 1",
                "Task 1",
                "KymaAgent",
                SubTaskStatus.PENDING,
                None,
                SubTaskStatus.COMPLETED,
            ),
            (
                "Task 2",
                "Task 2",
                "KymaAgent",
                SubTaskStatus.PENDING,
                "Result",
                SubTaskStatus.COMPLETED,
            ),
        ],
    )
    def test_complete(
        self, description, task_title, assigned_to, status, result, expected_status
    ):
        subtask = SubTask(
            description=description,
            task_title=task_title,
            assigned_to=assigned_to,
            status=status,
            result=result,
        )
        subtask.complete()
        assert subtask.status == expected_status


class TestCompanionState:
    @pytest.mark.parametrize(
        "messages, messages_summary, expected",
        [
            # Test case when messages_summary is not empty, should add the previous summary as first message.
            (
                [
                    AIMessage(content="Message 1", id="1"),
                    AIMessage(content="Message 2", id="2"),
                ],
                "Summary message",
                [
                    SystemMessage(content="Summary message"),
                    AIMessage(content="Message 1", id="1"),
                    AIMessage(content="Message 2", id="2"),
                ],
            ),
            # Test case when messages_summary is empty, should not add the previous summary as first message.
            (
                [
                    AIMessage(content="Message 1", id="1"),
                    AIMessage(content="Message 2", id="2"),
                ],
                "",
                [
                    AIMessage(content="Message 1", id="1"),
                    AIMessage(content="Message 2", id="2"),
                ],
            ),
        ],
    )
    def test_get_messages_including_summary(self, messages, messages_summary, expected):
        # given
        state = CompanionState(
            input=None,
            messages=messages,
            messages_summary=messages_summary,
            next=None,
            subtasks=[],
            error=None,
            k8s_client=None,
        )
        # when
        result = state.get_messages_including_summary()
        # then
        assert len(result) == len(expected)


class TestAgentState:
    # Test data for AgentState
    @pytest.mark.parametrize(
        "messages, next, subtasks, final_response, expected",
        [
            (
                [],
                None,
                [
                    SubTask(
                        description="Task 1",
                        task_title="Task 1",
                        assigned_to="KymaAgent",
                        status=SubTaskStatus.COMPLETED,
                    ),
                    SubTask(
                        description="Task 2",
                        task_title="Task 2",
                        assigned_to="KubernetesAgent",
                        status=SubTaskStatus.COMPLETED,
                    ),
                ],
                "",
                True,
            ),
            (
                [],
                None,
                [
                    SubTask(
                        description="Task 1",
                        task_title="Task 1",
                        assigned_to="KymaAgent",
                        status=SubTaskStatus.COMPLETED,
                    ),
                    SubTask(
                        description="Task 2",
                        task_title="Task 2",
                        assigned_to="KubernetesAgent",
                        status=SubTaskStatus.PENDING,
                    ),
                ],
                "",
                False,
            ),
        ],
    )
    @pytest.mark.parametrize(
        "messages, messages_summary, expected",
        [
            # Test case when messages_summary is not empty, should add the previous summary as first message.
            (
                [
                    AIMessage(content="Message 1", id="1"),
                    AIMessage(content="Message 2", id="2"),
                ],
                "Summary message",
                [
                    SystemMessage(content="Summary message"),
                    AIMessage(content="Message 1", id="1"),
                    AIMessage(content="Message 2", id="2"),
                ],
            ),
            # Test case when messages_summary is empty, should not add the previous summary as first message.
            (
                [
                    AIMessage(content="Message 1", id="1"),
                    AIMessage(content="Message 2", id="2"),
                ],
                "",
                [
                    AIMessage(content="Message 1", id="1"),
                    AIMessage(content="Message 2", id="2"),
                ],
            ),
        ],
    )
    def test_get_agent_messages_including_summary(
        self, messages, messages_summary, expected
    ):
        # given
        state = BaseAgentState(
            messages=[],
            messages_summary="",
            agent_messages=messages,
            agent_messages_summary=messages_summary,
            k8s_client=Mock(spec=IK8sClient),
            subtasks=[],
            my_task=None,
            is_last_step=False,
        )

        # when
        result = state.get_agent_messages_including_summary()

        # then
        assert len(result) == len(expected)


class TestUserInput:
    @pytest.mark.parametrize(
        "user_input, expected",
        [
            (
                UserInput(query="non-empty"),
                {},
            ),
            (
                UserInput(
                    query="non-empty",
                    resource_kind="Pod",
                    resource_api_version="v1",
                    resource_name="pod-1",
                    namespace="default",
                ),
                {
                    "resource_api_version": "v1",
                    "resource_kind": "Pod",
                    "resource_name": "pod-1",
                    "resource_namespace": "default",
                },
            ),
            (
                UserInput(
                    query="non-empty",
                    resource_kind="Pod",
                    resource_api_version="v1",
                    resource_name="pod-1",
                    namespace="",
                ),
                {
                    "resource_api_version": "v1",
                    "resource_kind": "Pod",
                    "resource_name": "pod-1",
                },
            ),
            (
                UserInput(
                    query="non-empty",
                    resource_kind="Pod",
                ),
                {
                    "resource_kind": "Pod",
                },
            ),
        ],
    )
    def test_get_resource_information(self, user_input, expected):
        assert user_input.get_resource_information() == expected
