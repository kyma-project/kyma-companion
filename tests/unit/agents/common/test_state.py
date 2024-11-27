import pytest

from agents.common.state import CompanionState, SubTask, SubTaskStatus, UserInput


class TestSubTask:
    # Test data for SubTask
    @pytest.mark.parametrize(
        "description, assigned_to, status, result, expected_status",
        [
            ("Task 1", "Agent A", SubTaskStatus.PENDING, None, SubTaskStatus.COMPLETED),
            (
                "Task 2",
                "Agent B",
                SubTaskStatus.PENDING,
                "Result",
                SubTaskStatus.COMPLETED,
            ),
        ],
    )
    def test_complete(self, description, assigned_to, status, result, expected_status):
        subtask = SubTask(
            description=description,
            assigned_to=assigned_to,
            status=status,
            result=result,
        )
        subtask.complete()
        assert subtask.status == expected_status


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
                        assigned_to="Agent A",
                        status=SubTaskStatus.COMPLETED,
                    ),
                    SubTask(
                        description="Task 2",
                        assigned_to="Agent B",
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
                        assigned_to="Agent A",
                        status=SubTaskStatus.COMPLETED,
                    ),
                    SubTask(
                        description="Task 2",
                        assigned_to="Agent B",
                        status=SubTaskStatus.PENDING,
                    ),
                ],
                "",
                False,
            ),
        ],
    )
    def test_all_tasks_completed(
        self, messages, next, subtasks, final_response, expected
    ):
        state = CompanionState(
            messages=messages,
            next=next,
            subtasks=subtasks,
            final_response=final_response,
        )
        assert state.all_tasks_completed() == expected


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
