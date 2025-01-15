from collections.abc import Sequence
from unittest.mock import MagicMock, Mock, patch

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import MessagesPlaceholder

from agents.common.agent import agent_edge, subtask_selector_edge
from agents.common.state import CompanionState, SubTask, SubTaskStatus
from agents.common.utils import (
    RECENT_MESSAGES_LIMIT,
    agent_node,
    compute_messages_token_count,
    compute_string_token_count,
    create_agent,
    filter_messages,
)
from agents.k8s.agent import K8S_AGENT
from agents.k8s.state import KubernetesAgentState
from services.k8s import IK8sClient
from utils.models.factory import ModelType

# Mock the logging setup
mock_logger = Mock()
mock_get_logger = Mock(return_value=Mock())


@pytest.fixture
def mock_llm():
    return Mock()


@pytest.fixture
def mock_tools():
    return [Mock(), Mock()]


@pytest.mark.parametrize(
    "system_prompt",
    [
        "You are a helpful assistant",
        "You are an AI language model",
        "",
    ],
)
@patch("agents.common.utils.get_logger", Mock())
def test_create_agent(mock_llm, mock_tools, system_prompt):
    with (
        patch(
            "agents.common.utils.OpenAIFunctionsAgent.from_llm_and_tools"
        ) as mock_from_llm_and_tools,
        patch("agents.common.utils.AgentExecutor") as mock_agent_executor,
    ):
        mock_agent = Mock()
        mock_from_llm_and_tools.return_value = mock_agent

        result = create_agent(mock_llm, mock_tools, system_prompt)

        mock_from_llm_and_tools.assert_called_once_with(
            mock_llm,
            mock_tools,
            extra_prompt_messages=[
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ],
            system_message=SystemMessage(content=system_prompt),
        )
        mock_agent_executor.assert_called_once_with(agent=mock_agent, tools=mock_tools)
        assert result == mock_agent_executor.return_value


@pytest.fixture
def mock_agent_executor():
    return Mock()


@pytest.fixture
def mock_state():
    return Mock(spec=CompanionState, messages=[HumanMessage(content="Hello Test")])


@pytest.mark.parametrize(
    "name, subtasks, agent_output, expected_result, should_complete",
    [
        # Successful execution
        (
            "agent1",
            [
                Mock(
                    spec=SubTask,
                    assigned_to="agent1",
                    description="Test task",
                    status=SubTaskStatus.PENDING,
                )
            ],
            {"output": "Task completed successfully"},
            {
                "messages": [
                    AIMessage(
                        content="Task completed successfully",
                        name="agent1",
                    )
                ]
            },
            True,
        ),
        # Execution error
        (
            "agent2",
            [
                Mock(
                    spec=SubTask,
                    assigned_to="agent2",
                    description="Error task",
                    status=SubTaskStatus.PENDING,
                )
            ],
            Exception("Test error"),
            {
                "error": "Test error",
                "next": "Exit",
            },
            False,
        ),
        # No matching subtask
        (
            "agent3",
            [
                Mock(
                    spec=SubTask,
                    assigned_to="other_agent",
                    description="Other task",
                    status=SubTaskStatus.PENDING,
                )
            ],
            None,
            {
                "messages": [
                    AIMessage(
                        content="All my subtasks are already completed.", name="agent3"
                    )
                ]
            },
            False,
        ),
        # Multiple subtasks (only first one should be executed)
        (
            "agent4",
            [
                Mock(
                    spec=SubTask,
                    assigned_to="agent4",
                    description="Task 1",
                    status=SubTaskStatus.COMPLETED,
                ),
                Mock(
                    spec=SubTask,
                    assigned_to="agent4",
                    description="Task 2",
                    status=SubTaskStatus.PENDING,
                ),
            ],
            {"output": "Task 2 completed"},
            {
                "messages": [
                    AIMessage(
                        content="Task 2 completed",
                        name="agent4",
                    )
                ]
            },
            True,
        ),
        (
            "agent5",
            [
                Mock(
                    spec=SubTask,
                    assigned_to="agent4",
                    description="Task 1",
                    status=SubTaskStatus.COMPLETED,
                ),
                Mock(
                    spec=SubTask,
                    assigned_to="agent4",
                    description="Task 2",
                    status=SubTaskStatus.COMPLETED,
                ),
            ],
            {"output": "Task 1 completed"},
            {
                "messages": [
                    AIMessage(
                        content="All my subtasks are already completed.", name="agent5"
                    )
                ]
            },
            False,
        ),
    ],
)
@patch("agents.common.utils.get_logger", Mock())
def test_agent_node(
    mock_agent_executor,
    mock_state,
    name,
    subtasks,
    agent_output,
    expected_result,
    should_complete,
):
    # Setup
    mock_state.subtasks = subtasks
    if isinstance(agent_output, Exception):
        mock_agent_executor.invoke.side_effect = agent_output
    else:
        mock_agent_executor.invoke.return_value = agent_output

    # Execute
    result = agent_node(mock_state, mock_agent_executor, name)

    # Assert
    assert result == expected_result

    not_completed_subtasks = [
        subtask for subtask in subtasks if subtask.status != SubTaskStatus.COMPLETED
    ]
    for not_completed_subtask in not_completed_subtasks:
        if subtasks and not_completed_subtask.assigned_to == name:
            mock_agent_executor.invoke.assert_called_once_with(
                {
                    "messages": mock_state.messages,
                    "input": not_completed_subtask.description,
                }
            )
            if should_complete:
                not_completed_subtask.complete.assert_called_once()
            else:
                not_completed_subtask.complete.assert_not_called()
        else:
            mock_agent_executor.invoke.assert_not_called()

    completed_subtasks = [
        subtask for subtask in subtasks if subtask.status == SubTaskStatus.COMPLETED
    ]
    for completed_subtask in completed_subtasks:
        completed_subtask.complete.assert_not_called()


@pytest.mark.parametrize(
    "messages, last_messages_number, expected_output",
    [
        # Test case 1: Less messages than the limit
        (
            [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
            10,
            [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
        ),
        # Test case 2: Exactly the number of messages as the limit
        (
            [
                HumanMessage(content="A"),
                AIMessage(content="B"),
                HumanMessage(content="C"),
            ],
            3,
            [
                HumanMessage(content="A"),
                AIMessage(content="B"),
                HumanMessage(content="C"),
            ],
        ),
        # Test case 3: More messages than the limit
        (
            [
                SystemMessage(content="System"),
                HumanMessage(content="1"),
                AIMessage(content="2"),
                HumanMessage(content="3"),
                AIMessage(content="4"),
            ],
            2,
            [HumanMessage(content="3"), AIMessage(content="4")],
        ),
        # Test case 4: Empty input
        ([], 5, []),
        # Test case 5: Custom last_messages_number
        (
            [
                HumanMessage(content="A"),
                AIMessage(content="B"),
                HumanMessage(content="C"),
                AIMessage(content="D"),
                HumanMessage(content="E"),
            ],
            4,
            [
                AIMessage(content="B"),
                HumanMessage(content="C"),
                AIMessage(content="D"),
                HumanMessage(content="E"),
            ],
        ),
        # Test case 6: last_messages_number = 1
        (
            [
                HumanMessage(content="First"),
                AIMessage(content="Second"),
                HumanMessage(content="Third"),
            ],
            1,
            [HumanMessage(content="Third")],
        ),
        # Test case 7: Tool messages on head of result list.
        (
            [
                AIMessage(content="Second"),
                ToolMessage(content="Tool message 1", tool_call_id="call_MEOW"),
                ToolMessage("Tool message 2", tool_call_id="call_WOF"),
                HumanMessage(content="First"),
                AIMessage(content="Second"),
                HumanMessage(content="Third"),
            ],
            5,
            [
                HumanMessage(content="First"),
                AIMessage(content="Second"),
                HumanMessage(content="Third"),
            ],
        ),
    ],
)
def test_filter_messages(
    messages: Sequence[BaseMessage],
    last_messages_number: int,
    expected_output: Sequence[BaseMessage],
):
    result = filter_messages(messages, last_messages_number)

    assert len(result) == len(expected_output)
    for res_msg, exp_msg in zip(result, expected_output, strict=False):
        assert type(res_msg) == type(exp_msg)
        assert res_msg.content == exp_msg.content


def test_filter_messages_default_parameter():
    messages = [HumanMessage(content=str(i)) for i in range(15)]
    result = filter_messages(messages)  # Using default last_messages_number
    assert len(result) == RECENT_MESSAGES_LIMIT
    assert [msg.content for msg in result] == [str(i) for i in range(5, 15)]


@pytest.mark.parametrize(
    "is_last_step, my_task, expected_output",
    [
        (
            False,
            SubTask(description="test", assigned_to=K8S_AGENT),
            "agent",
        ),
        (
            True,
            None,
            "finalizer",
        ),
    ],
)
def test_subtask_selector_edge(
    is_last_step: bool, my_task: SubTask | None, expected_output: str
):
    k8s_client = MagicMock()
    k8s_client.mock_add_spec(IK8sClient)

    state = KubernetesAgentState(
        my_task=my_task,
        is_last_step=is_last_step,
        messages=[],
        agent_messages=[],
        subtasks=[],
        k8s_client=k8s_client,
    )
    assert subtask_selector_edge(state) == expected_output


@pytest.mark.parametrize(
    "last_message, expected_output",
    [
        (
            ToolMessage(
                content="test",
                tool_call_id="call_MEOW",
                tool_calls={"call_MEOW": "test"},
            ),
            "tools",
        ),
        (
            AIMessage(content="test"),
            "finalizer",
        ),
    ],
)
def test_agent_edge(last_message: BaseMessage, expected_output: str):
    k8s_client = MagicMock()
    k8s_client.mock_add_spec(IK8sClient)

    state = KubernetesAgentState(
        my_task=None,
        is_last_step=False,
        messages=[],
        agent_messages=[last_message],
        subtasks=[],
        k8s_client=k8s_client,
    )
    assert agent_edge(state) == expected_output


@pytest.mark.parametrize(
    "text, model_type, expected_token_count",
    [
        ("Hello, world!", ModelType.GPT4O, 4),
        ("This is a test.", ModelType.GPT4O, 5),  # Example token count
        ("", ModelType.GPT4O, 0),  # Empty string
        (
            "A longer text input to test the token count.",
            ModelType.GPT4O,
            10,
        ),  # Example token count
    ],
)
def test_compute_string_token_count(text, model_type, expected_token_count):
    assert compute_string_token_count(text, model_type) == expected_token_count


@pytest.mark.parametrize(
    "msgs, model_type, expected_token_count",
    [
        (
            [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
            ModelType.GPT4O,
            3,  # Example token count
        ),
        (
            [
                HumanMessage(content="This is a test."),
                AIMessage(content="Another test."),
            ],
            ModelType.GPT4O,
            8,  # Example token count
        ),
        ([], ModelType.GPT4O, 0),  # No messages
        (
            [HumanMessage(content="A longer text input to test the token count.")],
            ModelType.GPT4O,
            10,  # Example token count
        ),
    ],
)
def test_compute_messages_token_count(msgs, model_type, expected_token_count):
    assert compute_messages_token_count(msgs, model_type) == expected_token_count
