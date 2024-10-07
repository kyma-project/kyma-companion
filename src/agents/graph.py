import json
from collections.abc import Hashable
from typing import Any, AsyncIterator, Dict, Literal, Protocol  # noqa UP

from langchain_core.messages import RemoveMessage, BaseMessage
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
from utils.models import IModel

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

    def aadd_messages(self, conversation_id: str, messages: list[BaseMessage]) -> None:
        """Add messages to the graph state."""
        ...

    def aget_messages(self, conversation_id: str) -> list[BaseMessage]:
        """Get messages from the graph state."""
        ...


class KymaGraph:
    """Kyma graph class. Represents all the workflow of the application."""

    model: IModel
    memory: BaseCheckpointSaver
    supervisor_agent: IAgent
    kyma_agent: IAgent
    k8s_agent: IAgent
    members: list[str] = []

    plan_parser = PydanticOutputParser(pydantic_object=Plan)  # type: ignore

    def __init__(self, model: IModel, memory: BaseCheckpointSaver):
        self.model = model
        self.memory = memory

        self.kyma_agent = KymaAgent(model)
        self.k8s_agent = KubernetesAgent(model)
        self.supervisor_agent = SupervisorAgent(
            model, members=[KYMA_AGENT, K8S_AGENT, COMMON]
        )

        self.members = [self.kyma_agent.name, self.k8s_agent.name, COMMON]
        self.graph = self._build_graph()

    def _create_planner_chain(self) -> RunnableSequence:
        planner_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", PLANNER_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            members=", ".join(self.members),
            output_format=self.plan_parser.get_format_instructions(),
        )
        return planner_prompt | self.model.llm  # type: ignore

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

        planner_chain = self._create_planner_chain()
        try:
            plan_response = planner_chain.invoke(
                input={
                    "messages": filter_messages(state.messages),
                },  # last message is the user query
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
                    content=f"Task decomposed into subtasks and assigned to agents: "
                    f"{json.dumps(plan.subtasks, cls=CustomJSONEncoder)}",
                    name=PLANNER,
                ),
                next=CONTINUE,
                subtasks=plan.subtasks,
            )
        except Exception as e:
            logger.error(f"Error in planning: {e}")
            return create_node_output(next=EXIT, error=str(e))

    def _common_node_chain(self) -> RunnableSequence:
        """Common node chain to handle general queries."""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", COMMON_QUESTION_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("human", "query: {query}"),
            ]
        )
        return prompt | self.model.llm  # type: ignore

    def common_node(self, state: AgentState) -> dict[str, Any]:
        """Common node to handle general queries."""

        chain = self._common_node_chain()

        for subtask in state.subtasks:
            if subtask.assigned_to == COMMON and subtask.status != "completed":
                try:
                    response = chain.invoke(
                        {
                            "messages": filter_messages(state.messages),
                            "query": subtask.description,
                        },
                    ).content
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

    def generate_final_response(self, state: AgentState) -> dict[str, Any]:
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
        workflow.add_node(FINALIZER, self.generate_final_response)
        workflow.add_node(KYMA_AGENT, self.kyma_agent.agent_node())
        workflow.add_node(K8S_AGENT, self.k8s_agent.agent_node())
        workflow.add_node(COMMON, self.common_node)

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

        # check if the request is related to the same Kubernetes resource.
        thread_id = {
            "configurable": {
                "thread_id": conversation_id,
            },
        }

        latest_state = await self.graph.aget_state(thread_id)
        if (latest_state.values
                and 'input' in latest_state.values
                and not user_input.is_same_resource(latest_state.values['input'])):
            # option 1: remove all messages. Pre-requisite is that all
            # the messages stored in the checkpoint should have valid ids i.e. message.id.
            # Tip: Use `add_messages` in graph state, because it sets the id of messages if missing.
            # e.g. messages: Annotated[Sequence[BaseMessage], add_messages]
            await self.graph.aupdate_state(thread_id, {
                "messages": [RemoveMessage(id=m.id) for m in latest_state.values['messages']],
            })

            # option 2: remove all previous checkpoints for the same thread_id.
            # self.memory.clear_checkpoint(thread_id)

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

    async def aadd_messages(self, conversation_id: str, messages: list[BaseMessage]) -> None:
        """Add messages to the graph state."""
        await self.graph.aupdate_state({
            "configurable": {
                "thread_id": conversation_id,
            },
        }, {
            "messages": messages,
        })

    async def aget_messages(self, conversation_id: str) -> list[BaseMessage]:
        """Get messages from the graph state."""
        latest_state = await self.graph.aget_state({
            "configurable": {
                "thread_id": conversation_id,
            },
        })
        if latest_state.values and 'messages' in latest_state.values:
            return latest_state.values['messages']
        return []