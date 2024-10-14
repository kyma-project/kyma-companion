import json
from collections.abc import Hashable
from typing import Any, AsyncIterator, Dict, Literal, Protocol, Sequence  # noqa UP

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph

from agents.common.agent import IAgent
from agents.common.constants import (
    COMMON,
    CONTINUE,
    ERROR,
    EXIT,
    FINAL_RESPONSE,
    MESSAGES,
    NEXT,
    PLANNER,
)
from agents.common.data import Message
from agents.common.state import AgentState, Plan, SubTask, UserInput
from agents.common.utils import (
    create_node_output,
    exit_node,
    filter_messages,
    next_step,
)
from agents.k8s.agent import K8S_AGENT, KubernetesAgent
from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.prompts import COMMON_QUESTION_PROMPT, FINALIZER_PROMPT, PLANNER_PROMPT
from agents.supervisor.agent import FINALIZER, SUPERVISOR, SupervisorAgent
from services.k8s import IK8sClient
from utils.langfuse import handler
from utils.logging import get_logger
from utils.models import LLM, IModel

logger = get_logger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for AIMessage, HumanMessage, and SubTask.
    Default JSON cannot serialize these objects.
    """

    def default(self, obj):  # noqa D102
        if isinstance(
            obj, AIMessage | HumanMessage | SystemMessage | ToolMessage | SubTask
        ):
            return obj.__dict__
        elif isinstance(obj, IK8sClient):
            return obj.model_dump()
        return super().default(obj)


class IGraph(Protocol):
    """Graph interface."""

    def astream(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        ...


class KymaGraph:
    """Kyma graph class. Represents all the workflow of the application."""

    models: dict[str, IModel]
    memory: BaseCheckpointSaver
    supervisor_agent: IAgent
    kyma_agent: IAgent
    k8s_agent: IAgent
    members: list[str] = []

    plan_parser = PydanticOutputParser(pydantic_object=Plan)  # type: ignore

    planner_prompt: ChatPromptTemplate

    def __init__(self, models: dict[str, IModel], memory: BaseCheckpointSaver):
        self.models = models
        self.memory = memory

        self.kyma_agent = KymaAgent(models.get(LLM.GPT4O_MINI))
        self.k8s_agent = KubernetesAgent(models.get(LLM.GPT4O))
        self.supervisor_agent = SupervisorAgent(
            models.get(LLM.GPT4O), members=[KYMA_AGENT, K8S_AGENT, COMMON]
        )

        self.members = [self.kyma_agent.name, self.k8s_agent.name, COMMON]
        self._planner_chain = self._planner_chain(models.get(LLM.GPT4O_MINI))
        self._common_node_chain = self._common_node_chain(models.get(LLM.GPT4O_MINI))
        self.graph = self._build_graph()

    def _planner_chain(self, model: IModel) -> RunnableSequence:
        self.planner_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", PLANNER_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            members=", ".join(self.members),
            output_format=self.plan_parser.get_format_instructions(),
        )
        return self.planner_prompt | model.llm  # type: ignore

    def _invoke_planner(self, state: AgentState) -> dict[str, Any]:
        """Invoke the planner."""
        return self._planner_chain.invoke(
            input={
                "messages": filter_messages(state.messages),
            },
        )

    def _plan(self, state: AgentState) -> dict[str, Any]:
        """
        Breaks down the given user query into sub-tasks if the query is related to Kyma and K8s.
        If the query is general, it returns the response directly.

        Args:
            state: AgentState: agent state of the Supervisor graph

        Returns:
            dict[str, Any]: output of the node with subtask if query is related to Kyma and K8s.
            Returns response directly if query is general.
        """

        # to prevent stored errors from previous runs
        state.error = None

        try:
            plan_response = self._invoke_planner(
                state,  # last message is the user query
            )

            try:
                plan = self.plan_parser.parse(plan_response.content)
                if plan.response:
                    return create_node_output(
                        message=AIMessage(content=plan.response, name=PLANNER),
                        final_response=plan.response,
                        next=EXIT,
                    )
            except OutputParserException as ope:
                logger.debug(f"Problem in parsing the planner response: {ope}")
                # If 'response' field of the content of plan_response is missing due to LLM inconsistency,
                # the response is read from the plan_response content.
                return create_node_output(
                    message=AIMessage(content=plan_response.content, name=PLANNER),
                    final_response=plan_response.content,
                    next=EXIT,
                )

            if not plan.subtasks:
                raise Exception(
                    f"No subtasks are created for the given query: {state.messages[-1].content}"
                )

            return create_node_output(
                message=AIMessage(
                    content=plan_response.content,
                    name=PLANNER,
                ),
                next=CONTINUE,
                subtasks=plan.subtasks,
            )
        except Exception as e:
            logger.error(f"Error in planning: {e}")
            return create_node_output(next=EXIT, error=str(e))

    @staticmethod
    def _common_node_chain(model: IModel) -> RunnableSequence:
        """Common node chain to handle general queries."""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", COMMON_QUESTION_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("human", "query: {query}"),
            ]
        )
        return prompt | model.llm  # type: ignore

    def _invoke_common_node(self, state: AgentState, subtask: str) -> str:
        """Invoke the common node."""
        return self._common_node_chain.invoke(
            {
                "messages": filter_messages(state.messages),
                "query": subtask,
            },
        ).content

    def _common_node(self, state: AgentState) -> dict[str, Any]:
        """Common node to handle general queries."""

        for subtask in state.subtasks:
            if subtask.assigned_to == COMMON and subtask.status != "completed":
                try:
                    response = self._invoke_common_node(state, subtask.description)
                    subtask.complete()
                    return {
                        MESSAGES: [
                            AIMessage(
                                content=response,
                                name=COMMON,
                            )
                        ],
                    }
                except Exception as e:
                    logger.error(f"Error in common node: {e}")
                    return {
                        ERROR: str(e),
                        NEXT: EXIT,
                    }
        return {
            MESSAGES: [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=COMMON,
                )
            ]
        }

    def _final_response_chain(self, state: AgentState) -> RunnableSequence:
        prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                ("system", FINALIZER_PROMPT),
            ]
        ).partial(members=", ".join(self.members), query=state.input.query)
        return prompt | self.model.llm  # type: ignore

    def _generate_final_response(self, state: AgentState) -> dict[str, Any]:
        """Generate the final response."""

        final_response_chain = self._final_response_chain(state)

        try:
            final_response = final_response_chain.invoke(
                {"messages": filter_messages(state.messages)},
            ).content

            return {
                MESSAGES: [
                    AIMessage(
                        content=final_response if final_response else "",
                        name=FINALIZER,
                    )
                ],
                NEXT: END,
                FINAL_RESPONSE: final_response,
            }
        except Exception as e:
            logger.error(f"Error in generating final response: {e}")
            return {
                ERROR: str(e),
                NEXT: EXIT,
            }

    def _build_graph(self) -> CompiledGraph:
        """Create a supervisor agent."""

        workflow = StateGraph(AgentState)
        workflow.add_node(FINALIZER, self._generate_final_response)
        workflow.add_node(KYMA_AGENT, self.kyma_agent.agent_node())
        workflow.add_node(K8S_AGENT, self.k8s_agent.agent_node())
        workflow.add_node(COMMON, self._common_node)

        workflow.add_node(SUPERVISOR, self.supervisor_agent.agent_node())
        workflow.add_node(PLANNER, self._plan)
        workflow.add_node(EXIT, exit_node)

        # routing to the exit node in case of an error
        workflow.add_conditional_edges(
            PLANNER,
            next_step,
            {EXIT: EXIT, CONTINUE: SUPERVISOR},
        )
        workflow.add_edge(EXIT, END)

        for member in self.members:
            # We want our workers to ALWAYS "report back" to the supervisor when done
            workflow.add_edge(member, SUPERVISOR)
        # The supervisor populates the "next" field in the graph state
        # which routes to a node or finishes
        conditional_map: dict[Hashable, str] = {
            k: k for k in self.members + [FINALIZER, EXIT]
        }
        workflow.add_conditional_edges(SUPERVISOR, lambda x: x.next, conditional_map)
        # Add end node
        workflow.add_edge(FINALIZER, EXIT)
        # Add entrypoint
        workflow.add_edge(START, PLANNER)

        graph = workflow.compile(checkpointer=self.memory)
        return graph

    async def astream(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        user_input = UserInput(**message.dict())
        messages = [
            SystemMessage(
                content=f"The user query is related to: {user_input.get_resource_information()}"
            ),
            HumanMessage(content=message.query),
        ]

        async for chunk in self.graph.astream(
            input={
                "messages": messages,
                "input": user_input,
                "k8s_client": k8s_client,
            },
            config={
                "configurable": {
                    "thread_id": conversation_id,
                },
                "callbacks": [handler],
            },
        ):
            chunk_json = json.dumps(chunk, cls=CustomJSONEncoder)
            if "__end__" not in chunk:
                yield chunk_json
