from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain_core.runnables import RunnableLambda
from langgraph.graph.graph import CompiledGraph

from agents.common.agent import BaseAgent
from agents.common.constants import AGENT_MESSAGES, ERROR
from agents.common.state import BaseAgentState, SubTask, SubTaskStatus
from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_query_tool
from services.k8s import IK8sClient
from utils.models.factory import IModel, ModelType

mock_agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a test agent"),
        MessagesPlaceholder(variable_name=AGENT_MESSAGES),
        ("human", "{query}"),
    ]
)


def mock_agent() -> BaseAgent:
    mock_model = MagicMock(spec=IModel)
    mock_model.name = ModelType.GPT4O
    return BaseAgent(
        name="KubernetesAgent",
        model=mock_model,
        tools=[k8s_query_tool, fetch_pod_logs_tool],
        agent_prompt=mock_agent_prompt,
        state_class=BaseAgentState,
    )


@pytest.fixture
def mock_graph():
    return Mock()


@pytest.fixture
def mock_k8s_client():
    return Mock(spec=IK8sClient)


class TestBaseAgent:
    """Test base agent class."""

    def test_agent_init(self):
        # Given
        agent = mock_agent()

        # Then
        assert agent.name == "KubernetesAgent"
        assert agent.tools == [k8s_query_tool, fetch_pod_logs_tool]
        assert agent.graph is not None
        assert agent.chain is not None

    def test_agent_node(self):
        # Given
        agent = mock_agent()

        # When
        result = agent.agent_node()

        # Then
        assert result is not None
        assert isinstance(result, CompiledGraph)

    def test_create_chain(self):
        # Given
        agent = mock_agent()
        excepted_amount_steps = 2
        expected_amount_messages = 3

        # When
        chain = agent._create_chain(mock_agent_prompt)

        # Then
        assert chain is not None
        assert len(chain.steps) == excepted_amount_steps

        # check step 1: chat prompt
        assert isinstance(chain.steps[0], ChatPromptTemplate)
        assert len(chain.steps[0].messages) == expected_amount_messages
        # check step 1 > message 1
        assert isinstance(chain.steps[0].messages[0], SystemMessagePromptTemplate)
        assert chain.steps[0].messages[0].prompt.template == "You are a test agent"
        # check step 1 > message 2
        assert isinstance(chain.steps[0].messages[1], MessagesPlaceholder)
        # check step 1 > message 3
        assert isinstance(chain.steps[0].messages[2], HumanMessagePromptTemplate)

        # check step 2: model
        assert isinstance(chain.steps[1], RunnableLambda)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case, given_state, expected_inputs",
        [
            (
                "Test case when agent_messages is empty, should use from messages field.",
                BaseAgentState(
                    is_last_step=False,
                    messages=[HumanMessage(content="What is K8s?")],
                    agent_messages=[],
                    subtasks=[],
                    k8s_client=Mock(spec=IK8sClient),
                    my_task=SubTask(
                        description="test 1",
                        task_title="test",
                        assigned_to="KubernetesAgent",
                    ),
                    remaining_steps=25,
                ),
                {
                    "agent_messages": [
                        HumanMessage(
                            content="What is K8s?",
                        )
                    ],
                    "query": "test 1",
                },
            ),
            (
                "Test case when agent_messages is non-empty, should use get_agent_messages_including_summary.",
                BaseAgentState(
                    is_last_step=False,
                    messages=[HumanMessage(content="What is K8s?")],
                    agent_messages=[HumanMessage(content="What is deployment?")],
                    agent_messages_summary="Summary of previous messages: K8s is orchestration tool. Deployment is workload resource.",
                    subtasks=[],
                    k8s_client=Mock(spec=IK8sClient),
                    my_task=SubTask(
                        description="test 2",
                        task_title="test",
                        assigned_to="KubernetesAgent",
                    ),
                    remaining_steps=25,
                ),
                {
                    "agent_messages": [
                        SystemMessage(
                            content="Summary of previous messages: K8s is orchestration tool. Deployment is workload resource.",
                        ),
                        HumanMessage(content="What is deployment?"),
                    ],
                    "query": "test 2",
                },
            ),
        ],
    )
    async def test_invoke_chain(
        self,
        test_case: str,
        given_state: BaseAgentState,
        expected_inputs: dict,
    ):
        # Given
        agent = mock_agent()
        agent.chain = Mock()
        agent.chain.ainvoke = AsyncMock()

        # When
        await agent._invoke_chain(given_state, {})

        # Then
        # Get the actual call arguments
        assert agent.chain.ainvoke.call_count == 1, test_case
        actual_call = agent.chain.ainvoke.call_args
        actual_input = actual_call.kwargs["input"]

        # Remove id field from messages for comparison as it is not deterministic
        actual_messages = actual_input.get("agent_messages", [])
        expected_messages = expected_inputs.get("agent_messages", [])
        for msg in actual_messages + expected_messages:
            msg.id = None
        assert actual_input == expected_inputs, test_case

    def test_build_graph(self):
        # Given
        agent = mock_agent()

        # When
        graph = agent._build_graph(BaseAgentState)

        # Then
        # Check nodes.
        node_number = 6
        assert len(graph.nodes) == node_number
        assert graph.nodes.keys() == {
            "__start__",
            "subtask_selector",
            "agent",
            "tools",
            "finalizer",
            "Summarization",
        }
        # Check edges.
        edge_number = 3
        assert len(graph.builder.edges) == edge_number
        assert graph.builder.edges == {
            ("__start__", "subtask_selector"),
            ("finalizer", "__end__"),
            ("tools", "Summarization"),
        }
        # Check conditional edges.
        branch_number = 3
        assert len(graph.builder.branches) == branch_number

    @pytest.mark.parametrize(
        "given_state, expected_output",
        [
            # Test case when there is a subtask assigned to the agent.
            (
                BaseAgentState(
                    remaining_steps=25,
                    my_task=None,
                    is_last_step=False,
                    messages=[],
                    agent_messages=[],
                    subtasks=[
                        SubTask(
                            description="test",
                            task_title="test",
                            assigned_to="KubernetesAgent",
                        ),
                        SubTask(
                            description="test",
                            task_title="test",
                            assigned_to="KubernetesAgent",
                        ),
                    ],
                    k8s_client=Mock(spec=IK8sClient),
                ),
                {
                    "my_task": SubTask(
                        description="test",
                        task_title="test",
                        assigned_to="KubernetesAgent",
                    ),
                },
            ),
            # Test case when there is no subtask assigned to the agent.
            (
                BaseAgentState(
                    remaining_steps=25,
                    my_task=None,
                    is_last_step=False,
                    messages=[],
                    agent_messages=[],
                    subtasks=[
                        SubTask(
                            description="test",
                            task_title="test",
                            assigned_to="KymaAgent",
                        ),
                    ],
                    k8s_client=Mock(spec=IK8sClient),
                ),
                {
                    "is_last_step": True,
                    AGENT_MESSAGES: [
                        AIMessage(
                            content="All my subtasks are already completed.",
                            name="KubernetesAgent",
                        )
                    ],
                },
            ),
            # Test case when there all subtasks assigned to the agent are completed.
            (
                BaseAgentState(
                    remaining_steps=25,
                    my_task=None,
                    is_last_step=False,
                    messages=[],
                    agent_messages=[],
                    subtasks=[
                        SubTask(
                            description="test",
                            task_title="test",
                            assigned_to="KymaAgent",
                        ),
                        SubTask(
                            description="test1",
                            task_title="test1",
                            assigned_to="KubernetesAgent",
                            status=SubTaskStatus.COMPLETED,
                        ),
                        SubTask(
                            description="test2",
                            task_title="test2",
                            assigned_to="KubernetesAgent",
                            status=SubTaskStatus.COMPLETED,
                        ),
                    ],
                    k8s_client=Mock(spec=IK8sClient),
                ),
                {
                    "is_last_step": True,
                    AGENT_MESSAGES: [
                        AIMessage(
                            content="All my subtasks are already completed.",
                            name="KubernetesAgent",
                        )
                    ],
                },
            ),
        ],
    )
    def test_subtask_selector_node(
        self, given_state: BaseAgentState, expected_output: dict
    ):
        # Given
        agent = mock_agent()

        # Then
        assert agent._subtask_selector_node(given_state) == expected_output

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "given_invoke_response, given_invoke_error, given_state, expected_output, expected_invoke_inputs",
        [
            # Test case when the model returns a response.
            (
                AIMessage(content="This is a dummy response from model."),
                None,
                BaseAgentState(
                    remaining_steps=25,
                    my_task=SubTask(
                        description="test task 1",
                        task_title="test task 1",
                        assigned_to="KubernetesAgent",
                    ),
                    is_last_step=False,
                    messages=[AIMessage(content="dummy message 1")],
                    agent_messages=[AIMessage(content="dummy message 1")],
                    k8s_client=Mock(spec=IK8sClient),
                ),
                {
                    AGENT_MESSAGES: [
                        AIMessage(
                            content="This is a dummy response from model.",
                            additional_kwargs={"owner": "KubernetesAgent"},
                        )
                    ]
                },
                {
                    AGENT_MESSAGES: [AIMessage(content="dummy message 1")],
                    "query": "test task 1",
                },
            ),
            # Test case when the model raises an exception.
            (
                None,
                ValueError("This is a dummy exception from model."),
                BaseAgentState(
                    remaining_steps=25,
                    my_task=SubTask(
                        description="test task 1",
                        task_title="test task 1",
                        assigned_to="KubernetesAgent",
                    ),
                    is_last_step=False,
                    messages=[AIMessage(content="dummy message 1")],
                    agent_messages=[AIMessage(content="dummy message 1")],
                    k8s_client=Mock(spec=IK8sClient),
                ),
                {
                    AGENT_MESSAGES: [
                        AIMessage(
                            content="Sorry, an unexpected error occurred while processing your request.Please try again later.",
                            name="KubernetesAgent",
                        )
                    ],
                    ERROR: "An error occurred while processing the request",
                },
                {
                    AGENT_MESSAGES: [AIMessage(content="dummy message 1")],
                    "query": "test task 1",
                },
            ),
            # Test case when the recursive limit is reached.
            (
                AIMessage(
                    content="This is a dummy response from model.",
                    tool_calls=[
                        {
                            "name": "test_tool",
                            "args": {"arg1": "value1"},
                            "id": "test_id",
                        }
                    ],
                ),
                None,
                BaseAgentState(
                    remaining_steps=25,
                    my_task=SubTask(
                        description="test task 1",
                        task_title="test task 1",
                        assigned_to="KubernetesAgent",
                    ),
                    is_last_step=True,
                    messages=[AIMessage(content="dummy message 1")],
                    agent_messages=[AIMessage(content="dummy message 1")],
                    k8s_client=Mock(spec=IK8sClient),
                ),
                {
                    AGENT_MESSAGES: [
                        AIMessage(
                            content="Sorry, I need more steps to process the request.",
                            name="KubernetesAgent",
                        )
                    ]
                },
                {
                    AGENT_MESSAGES: [AIMessage(content="dummy message 1")],
                    "query": "test task 1",
                },
            ),
        ],
    )
    async def test_model_node(
        self,
        mock_config,
        given_invoke_response: BaseMessage | None,
        given_invoke_error: Exception | None,
        given_state: BaseAgentState,
        expected_output: dict,
        expected_invoke_inputs: dict,
    ):
        # Given
        agent = mock_agent()
        agent.chain = AsyncMock()
        agent._invoke_chain = AsyncMock()
        if given_invoke_response:
            agent._invoke_chain.return_value = given_invoke_response
        elif given_invoke_error:
            agent._invoke_chain.side_effect = given_invoke_error

        # When
        result = await agent._model_node(given_state, mock_config)
        assert result == expected_output

        # Test if status is updated to ERROR when there is an exception
        if given_invoke_error and given_state.my_task and given_state.my_task.status:
            assert given_state.my_task.status == SubTaskStatus.ERROR

        # Then
        if expected_invoke_inputs != {}:
            agent._invoke_chain.assert_called_once_with(given_state, mock_config)

    @pytest.mark.parametrize(
        "given_state, expected_output",
        [
            # Test case when the subtask is completed. Should return last message from agent_messages.
            (
                BaseAgentState(
                    remaining_steps=25,
                    my_task=SubTask(
                        description="test task 1",
                        task_title="test task 1",
                        assigned_to="KubernetesAgent",
                        status=SubTaskStatus.PENDING,
                    ),
                    is_last_step=False,
                    messages=[],
                    agent_messages=[
                        AIMessage(
                            id="1",
                            content="dummy",
                            additional_kwargs={"owner": "KubernetesAgent"},
                            tool_calls=[
                                {
                                    "args": {
                                        "uri": "/api/v1/namespaces/default/secrets/test-user1-admin"
                                    },
                                    "id": "call_JZM1Sbccr9nQ49KLT21qG4W6",
                                    "name": "k8s_query_tool",
                                    "type": "tool_call",
                                }
                            ],
                        ),
                        ToolMessage(
                            id="2",
                            content="dummy",
                            name="k8s_query_tool",
                            tool_call_id="call_JZM1Sbccr9nQ49KLT21qG4W6",
                        ),
                        AIMessage(id="3", content="final answer"),
                    ],
                    k8s_client=Mock(spec=IK8sClient),
                ),
                {
                    "messages": [
                        AIMessage(id="3", content="final answer"),
                    ],
                    "subtasks": [],
                },
            ),
        ],
    )
    def test_finalizer_node(
        self,
        given_state: BaseAgentState,
        expected_output: dict,
    ):
        # Given
        agent = mock_agent()
        agent.chain = MagicMock()

        # When
        actual_output = agent._finalizer_node(state=given_state, config=Mock())

        # Then
        assert actual_output == expected_output
        if given_state.my_task and given_state.my_task.status:
            assert given_state.my_task.status == SubTaskStatus.COMPLETED
