from unittest.mock import MagicMock, Mock

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langgraph.graph.graph import CompiledGraph

from agents.common.constants import FINALIZER, MESSAGES
from agents.common.state import SubTask, SubTaskStatus
from agents.k8s.agent import KubernetesAgent
from agents.k8s.constants import IS_LAST_STEP, K8S_AGENT, MY_TASK
from agents.k8s.prompts import K8S_AGENT_PROMPT
from agents.k8s.state import KubernetesAgentState
from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_query_tool
from services.k8s import IK8sClient
from utils.models import IModel


@pytest.fixture
def mock_model():
    return Mock(spec=IModel)


@pytest.fixture
def mock_graph():
    return Mock()


@pytest.fixture
def mock_config():
    return Mock()


class TestKubernetesAgent:
    def test_name(self, mock_model):
        agent = KubernetesAgent(mock_model)
        assert agent.name == K8S_AGENT

    def test_agent_init(self, mock_model, mock_graph):
        agent = KubernetesAgent(mock_model)
        assert agent.tools == [k8s_query_tool, fetch_pod_logs_tool]
        assert agent.model == mock_model
        assert agent.graph is not None
        assert agent.chain is not None

    def test_agent_node(self, mock_model):
        # Given
        agent = KubernetesAgent(mock_model)

        # When
        result = agent.agent_node()

        # Then
        assert result is not None
        assert isinstance(result, CompiledGraph)

    def test_create_chain(self, mock_model):
        # Given
        agent = KubernetesAgent(mock_model)

        # When
        chain = agent._create_chain()

        # Then
        assert chain is not None
        assert len(chain.steps) == 2  # noqa

        # check step 1: chat prompt
        assert isinstance(chain.steps[0], ChatPromptTemplate) == True  # noqa
        assert len(chain.steps[0].messages) == 3  # noqa
        # check step 1 > message 1
        assert isinstance(chain.steps[0].messages[0], SystemMessage)
        assert chain.steps[0].messages[0].content == K8S_AGENT_PROMPT
        # check step 1 > message 2
        assert isinstance(chain.steps[0].messages[1], MessagesPlaceholder)
        # check step 1 > message 3
        assert isinstance(chain.steps[0].messages[2], HumanMessage)
        assert chain.steps[0].messages[2].content == "query: {query}"

        # check step 2: model
        assert isinstance(chain.steps[1], RunnableLambda)

    def test_build_graph(self, mock_model):
        # Given
        agent = KubernetesAgent(mock_model)

        # When
        graph = agent._build_graph()

        # Then
        # check nodes.
        assert len(graph.nodes) == 5  # noqa
        assert graph.nodes.keys() == {
            "__start__",
            "subtask_selector",
            "agent",
            "tools",
            "finalizer",
        }
        # check edges.
        assert len(graph.builder.edges) == 3  # noqa
        assert graph.builder.edges == {
            ("tools", "agent"),
            ("__start__", "subtask_selector"),
            ("finalizer", "__end__"),
        }
        # check conditional edges.
        assert len(graph.builder.branches) == 2  # noqa

    @pytest.mark.parametrize(
        "given_state, expected_output",
        [
            # Test case when there is a subtask assigned to the agent.
            (
                KubernetesAgentState(
                    my_task=None,
                    is_last_step=False,
                    messages=[],
                    subtasks=[
                        SubTask(description="test", assigned_to=FINALIZER),
                        SubTask(description="test", assigned_to=K8S_AGENT),
                    ],
                    k8s_client=Mock(spec_set=IK8sClient),
                ),
                {
                    MY_TASK: SubTask(description="test", assigned_to=K8S_AGENT),
                },
            ),
            # Test case when there is no subtask assigned to the agent.
            (
                KubernetesAgentState(
                    my_task=None,
                    is_last_step=False,
                    messages=[],
                    subtasks=[
                        SubTask(description="test", assigned_to=FINALIZER),
                    ],
                    k8s_client=Mock(spec_set=IK8sClient),
                ),
                {
                    IS_LAST_STEP: True,
                    MESSAGES: [
                        AIMessage(
                            content="All my subtasks are already completed.",
                            name=K8S_AGENT,
                        )
                    ],
                },
            ),
            # Test case when there all subtasks assigned to the agent are completed.
            (
                KubernetesAgentState(
                    my_task=None,
                    is_last_step=False,
                    messages=[],
                    subtasks=[
                        SubTask(description="test", assigned_to=FINALIZER),
                        SubTask(
                            description="test1",
                            assigned_to=K8S_AGENT,
                            status=SubTaskStatus.COMPLETED,
                        ),
                        SubTask(
                            description="test2",
                            assigned_to=K8S_AGENT,
                            status=SubTaskStatus.COMPLETED,
                        ),
                    ],
                    k8s_client=Mock(spec_set=IK8sClient),
                ),
                {
                    IS_LAST_STEP: True,
                    MESSAGES: [
                        AIMessage(
                            content="All my subtasks are already completed.",
                            name=K8S_AGENT,
                        )
                    ],
                },
            ),
        ],
    )
    def test_subtask_selector_node(
        self, mock_model, given_state: KubernetesAgentState, expected_output: dict
    ):
        agent = KubernetesAgent(mock_model)
        assert agent._subtask_selector_node(given_state) == expected_output

    @pytest.mark.parametrize(
        "given_invoke_response, given_invoke_error, given_state, expected_output, expected_invoke_inputs",
        [
            # Test case when the model returns a response.
            (
                AIMessage(content="This is a dummy response from model."),
                None,
                KubernetesAgentState(
                    my_task=SubTask(description="test task 1", assigned_to=K8S_AGENT),
                    is_last_step=False,
                    messages=[AIMessage(content="dummy message 1")],
                    k8s_client=Mock(spec_set=IK8sClient),
                ),
                {
                    MESSAGES: [
                        AIMessage(
                            content="This is a dummy response from model.",
                            additional_kwargs={"owner": "KubernetesAgent"},
                        )
                    ]
                },
                {
                    "messages": [AIMessage(content="dummy message 1")],
                    "query": "test task 1",
                },
            ),
            # Test case when the model raises an exception.
            (
                None,
                ValueError("This is a dummy exception from model."),
                KubernetesAgentState(
                    my_task=SubTask(description="test task 1", assigned_to=K8S_AGENT),
                    is_last_step=False,
                    messages=[AIMessage(content="dummy message 1")],
                    k8s_client=Mock(spec_set=IK8sClient),
                ),
                {
                    MESSAGES: [
                        AIMessage(
                            content="Sorry, I encountered an error while processing the request. "
                            "Error: This is a dummy exception from model.",
                        )
                    ]
                },
                {
                    "messages": [AIMessage(content="dummy message 1")],
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
                KubernetesAgentState(
                    my_task=SubTask(description="test task 1", assigned_to=K8S_AGENT),
                    is_last_step=True,
                    messages=[AIMessage(content="dummy message 1")],
                    k8s_client=Mock(spec_set=IK8sClient),
                ),
                {
                    MESSAGES: [
                        AIMessage(
                            content="Sorry, the kubernetes agent needs more steps to process the request.",
                        )
                    ]
                },
                {
                    "messages": [AIMessage(content="dummy message 1")],
                    "query": "test task 1",
                },
            ),
        ],
    )
    def test_model_node(
        self,
        mock_model,
        mock_config,
        given_invoke_response: BaseMessage,
        given_invoke_error: Exception,
        given_state: KubernetesAgentState,
        expected_output: dict,
        expected_invoke_inputs: dict,
    ):
        # Given
        agent = KubernetesAgent(mock_model)
        agent.chain = MagicMock()
        agent.chain.invoke = MagicMock()
        if given_invoke_response is not None:
            agent.chain.invoke.return_value = given_invoke_response
        elif given_invoke_error is not None:
            agent.chain.invoke.side_effect = given_invoke_error

        # When
        assert agent._model_node(given_state, mock_config) == expected_output

        # Then
        if expected_invoke_inputs != {}:
            agent.chain.invoke.assert_called_once_with(
                expected_invoke_inputs, mock_config
            )

    @pytest.mark.parametrize(
        "given_message, expected_output",
        [
            # Test case when the AIMessage have None additional_kwargs.
            (
                AIMessage(content="dummy"),
                False,
            ),
            # Test case when the AIMessage have no owner key in additional_kwargs.
            (
                AIMessage(content="dummy", additional_kwargs={"key": "value"}),
                False,
            ),
            # Test case when the AIMessage have different owner in additional_kwargs.
            (
                AIMessage(
                    content="dummy",
                    additional_kwargs={"owner": "value"},
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
                False,
            ),
            # Test case when the AIMessage have KubernetesAgent owner in additional_kwargs.
            (
                AIMessage(
                    content="dummy",
                    additional_kwargs={"owner": K8S_AGENT},
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
                True,
            ),
            # Test case when the ToolMessage have non-relevant tool name.
            (
                ToolMessage(
                    content="dummy",
                    name="google_query_tool",
                    tool_call_id="call_JZM1Sbccr9nQ49KLT21qG4W6",
                ),
                False,
            ),
            # Test case when the ToolMessage have relevant tool name.
            (
                ToolMessage(
                    content="dummy",
                    name="k8s_query_tool",
                    tool_call_id="call_JZM1Sbccr9nQ49KLT21qG4W6",
                ),
                True,
            ),
            # Test case when the ToolMessage have relevant tool name.
            (
                ToolMessage(
                    content="dummy",
                    name="fetch_pod_logs_tool",
                    tool_call_id="call_JZM1Sbccr9nQ49KLT21qG4W6",
                ),
                True,
            ),
        ],
    )
    def test_is_internal_message(
        self,
        mock_model,
        given_message: BaseMessage,
        expected_output: bool,
    ):
        # Given
        agent = KubernetesAgent(mock_model)

        # When
        assert agent.is_internal_message(given_message) == expected_output

    @pytest.mark.parametrize(
        "given_state, expected_output",
        [
            # Test case when the subtask is not completed and tool call messages exists.
            (
                KubernetesAgentState(
                    my_task=SubTask(
                        description="test task 1",
                        assigned_to=K8S_AGENT,
                        status=SubTaskStatus.PENDING,
                    ),
                    is_last_step=False,
                    messages=[
                        AIMessage(
                            id="1",
                            content="dummy",
                            additional_kwargs={"owner": K8S_AGENT},
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
                    k8s_client=Mock(spec_set=IK8sClient),
                ),
                {
                    "messages": [
                        RemoveMessage(content="", id="1"),
                        RemoveMessage(content="", id="2"),
                    ],
                    "my_task": None,
                },
            ),
        ],
    )
    def test_finalizer_node(
        self,
        mock_model,
        given_state: KubernetesAgentState,
        expected_output: dict,
    ):
        # Given
        agent = KubernetesAgent(mock_model)
        agent.chain = MagicMock()

        # When
        assert agent._finalizer_node(given_state, mock_config) == expected_output
        assert given_state.my_task.status == SubTaskStatus.COMPLETED
