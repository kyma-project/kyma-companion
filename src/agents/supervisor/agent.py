from typing import Any, Literal, cast

from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph
from pydantic import BaseModel, Field

from agents.common.constants import (
    COMMON,
    FINALIZER,
    K8S_AGENT,
    KYMA_AGENT,
    MESSAGES,
    NEXT,
    PLANNER,
)
from agents.common.state import Plan
from agents.common.utils import create_node_output, filter_messages
from agents.supervisor.prompts import (
    FINALIZER_PROMPT,
    FINALIZER_PROMPT_FOLLOW_UP,
    PLANNER_PROMPT,
)
from agents.supervisor.state import SupervisorState
from utils.filter_messages import (
    filter_messages_via_checks,
    is_finalizer_message,
    is_human_message,
    is_system_message,
)
from utils.logging import get_logger
from utils.models.factory import IModel, ModelType

SUPERVISOR = "Supervisor"
ROUTER = "Router"

logger = get_logger(__name__)


def decide_route_or_exit(state: SupervisorState) -> Literal[ROUTER, END]:  # type: ignore
    """Return the next node whether to route or exit with a direct response."""
    if state.next == END:
        logger.debug("Ending the workflow.")
        return END
    # if there is a recoverable error
    if state.error:
        logger.error(f"Exiting the workflow due to the error: {state.error}")
        return END

    return ROUTER


def decide_entry_point(state: SupervisorState) -> Literal[PLANNER, ROUTER, FINALIZER]:  # type: ignore
    """When entering the supervisor subgraph, decide the entry point: plan, route, or finalize."""

    # if all subtasks are completed, finalize the response
    if state.subtasks and all(subtask.completed() for subtask in state.subtasks):
        logger.debug("Finalizing as all subtasks are completed.")
        return FINALIZER

    # if subtasks exists but not all are completed, router delegates to the next agent
    if state.subtasks:
        logger.debug("No need to plan as subtasks are already created.")
        return ROUTER

    # if there are no subtasks, come up with a plan
    logger.debug("Breaking down the query into subtasks.")
    return PLANNER


class SupervisorAgent:
    """Supervisor agent class."""

    model: IModel
    _name: str = SUPERVISOR
    members: list[str] = []
    plan_parser = PydanticOutputParser(pydantic_object=Plan)

    def __init__(self, models: dict[str, IModel | Embeddings], members: list[str]):
        gpt_4o = cast(IModel, models[ModelType.GPT4O])

        self.model = gpt_4o
        self.members = members
        self.parser = self._route_create_parser()
        self._planner_chain = self._create_planner_chain(gpt_4o)
        self._graph = self._build_graph()

    def _get_members_str(self) -> str:
        return ", ".join(self.members)

    def _route_create_parser(self) -> PydanticOutputParser:
        class RouteResponse(BaseModel):
            next: Literal[*self.members] | None = Field(  # type: ignore
                description="next agent to be called"
            )

        return PydanticOutputParser(pydantic_object=RouteResponse)

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self) -> CompiledGraph:
        """Get Supervisor agent node function."""
        return self._graph

    def _route(self, state: SupervisorState) -> dict[str, Any]:
        """Router node. Routes the conversation to the next agent."""
        for subtask in state.subtasks:
            if not subtask.completed():
                next_agent = subtask.assigned_to
                return {
                    "next": next_agent,
                    "subtasks": state.subtasks,
                }
        return {
            "next": FINALIZER,
            "subtasks": state.subtasks,
        }

    def _create_planner_chain(self, model: IModel) -> RunnableSequence:
        self.planner_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", PLANNER_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            kyma_agent=KYMA_AGENT, kubernetes_agent=K8S_AGENT, common_agent=COMMON
        )
        return self.planner_prompt | model.llm.with_structured_output(Plan)  # type: ignore

    async def _invoke_planner(self, state: SupervisorState) -> Plan:
        """Invoke the planner."""

        filtered_messages = filter_messages_via_checks(
            state.messages, [is_human_message, is_system_message, is_finalizer_message]
        )
        reduces_messages = filter_messages(filtered_messages)

        plan: Plan = await self._planner_chain.ainvoke(
            input={
                "messages": reduces_messages,
            },
        )
        return plan

    async def _plan(self, state: SupervisorState) -> dict[str, Any]:
        """
        Breaks down the given user query into sub-tasks if the query is related to Kyma and K8s.
        If the query is general, it returns the response directly.
        """
        state.error = None

        try:
            plan = await self._invoke_planner(
                state,  # last message is the user query
            )

            # return the response if planner responded directly
            if plan.response:
                return create_node_output(
                    message=AIMessage(content=plan.response, name=PLANNER),
                    next=END,
                )

            # if the Planner did not respond directly but also failed to create any subtasks, raise an exception
            if not plan.subtasks:
                raise Exception(
                    f"No subtasks are created for the given query: {state.messages[-1].content}"
                )
            # return the plan with the subtasks to be dispatched by the Router
            return create_node_output(
                next=ROUTER,
                subtasks=plan.subtasks,
            )
        except Exception as e:
            logger.error(f"Error in planning: {e}")
            return {
                MESSAGES: [
                    AIMessage(
                        content=f"Sorry, I encountered an error while processing the request. Error: {e}",
                        name=PLANNER,
                    )
                ]
            }

    def _final_response_chain(self, state: SupervisorState) -> RunnableSequence:
        # last human message must be the query
        last_human_message = next(
            (msg for msg in reversed(state.messages) if isinstance(msg, HumanMessage)),
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", FINALIZER_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("system", FINALIZER_PROMPT_FOLLOW_UP),
            ]
        ).partial(members=self._get_members_str(), query=last_human_message.content)
        return prompt | self.model.llm  # type: ignore

    async def _generate_final_response(self, state: SupervisorState) -> dict[str, Any]:
        """Generate the final response."""

        final_response_chain = self._final_response_chain(state)

        try:
            final_response = await final_response_chain.ainvoke(
                {"messages": state.messages},
            )

            return {
                MESSAGES: [
                    AIMessage(
                        content=final_response.content,
                        name=FINALIZER,
                    )
                ],
                NEXT: END,
            }
        except Exception as e:
            logger.error(f"Error in generating final response: {e}")
            return {
                MESSAGES: [
                    AIMessage(
                        content=f"Sorry, I encountered an error while processing the request. Error: {e}",
                        name=FINALIZER,
                    )
                ]
            }

    def _build_graph(self) -> CompiledGraph:
        # Define a new graph.
        workflow = StateGraph(SupervisorState)

        # Define the nodes of the graph.
        workflow.add_node(PLANNER, self._plan)
        workflow.add_node(ROUTER, self._route)
        workflow.add_node(FINALIZER, self._generate_final_response)

        # Set the entrypoint: ENTRY --> (planner | router | finalizer)
        workflow.add_conditional_edges(
            START,
            decide_entry_point,
            {
                PLANNER: PLANNER,
                ROUTER: ROUTER,
                FINALIZER: FINALIZER,
            },
        )

        # Define the edge: planner --> (router | END)
        workflow.add_conditional_edges(
            PLANNER,
            decide_route_or_exit,
            {ROUTER: ROUTER, END: END},
        )

        # Define the edge: finalizer --> END
        workflow.add_edge(FINALIZER, END)

        return workflow.compile()
