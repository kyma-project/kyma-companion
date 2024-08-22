from unittest.mock import Mock, patch

import pytest
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import MessagesPlaceholder

from agents.common.state import AgentState, SubTask
from agents.common.utils import agent_node, create_agent

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
    return Mock(spec=AgentState)


@pytest.mark.parametrize(
    "name, subtasks, agent_output, expected_result, should_complete",
    [
        # Successful execution
        (
            "agent1",
            [Mock(spec=SubTask, assigned_to="agent1", description="Test task")],
            {"output": "Task completed successfully"},
            {
                "messages": [
                    AIMessage(content="Task completed successfully", name="agent1")
                ]
            },
            True,
        ),
        # Execution error
        (
            "agent2",
            [Mock(spec=SubTask, assigned_to="agent2", description="Error task")],
            Exception("Test error"),
            {
                "messages": [
                    AIMessage(
                        content="Error in agent agent2: Test error", name="agent2"
                    )
                ]
            },
            False,
        ),
        # No matching subtask
        (
            "agent3",
            [Mock(spec=SubTask, assigned_to="other_agent", description="Other task")],
            None,
            {"messages": []},
            False,
        ),
        # Multiple subtasks (only first one should be executed)
        (
            "agent4",
            [
                Mock(spec=SubTask, assigned_to="agent4", description="Task 1"),
                Mock(spec=SubTask, assigned_to="agent4", description="Task 2"),
            ],
            {"output": "Task 1 completed"},
            {"messages": [AIMessage(content="Task 1 completed", name="agent4")]},
            True,
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

    if subtasks and subtasks[0].assigned_to == name:
        mock_agent_executor.invoke.assert_called_once_with(
            {"input": subtasks[0].description}
        )
        if should_complete:
            subtasks[0].complete.assert_called_once()
        else:
            subtasks[0].complete.assert_not_called()
    else:
        mock_agent_executor.invoke.assert_not_called()

    # Check that only the first matching subtask was processed
    if len(subtasks) > 1 and subtasks[1].assigned_to == name:
        subtasks[1].complete.assert_not_called()
