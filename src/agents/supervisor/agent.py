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
from agents.common.exceptions import SubtasksMissingError
from agents.common.response_converter import IResponseConverter, ResponseConverter
from agents.common.state import Plan
from agents.common.utils import create_node_output, filter_messages
from agents.supervisor.prompts import (
    FINALIZER_PROMPT,
    FINALIZER_PROMPT_FOLLOW_UP,
    PLANNER_STEP_INSTRUCTIONS,
    PLANNER_SYSTEM_PROMPT,
)
from agents.supervisor.state import SupervisorState
from utils.chain import ainvoke_chain
from utils.filter_messages import (
    filter_messages_via_checks,
    is_ai_message,
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

    # if no subtasks is pending, finalize the response
    if state.subtasks and all(not subtask.is_pending() for subtask in state.subtasks):
        logger.debug("Routing to Finilizer as no subtasks is pending.")
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

    def __init__(
        self,
        models: dict[str, IModel | Embeddings],
        members: list[str],
        response_converter: IResponseConverter | None = None,
    ) -> None:
        self.model = cast(IModel, models[ModelType.GPT4O_MINI])
        self.members = members
        self.parser = self._route_create_parser()
        self.response_converter: IResponseConverter = (
            response_converter or ResponseConverter()
        )
        self._planner_chain = self._create_planner_chain(self.model)
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

        # Check for pending subtasks
        for subtask in state.subtasks:
            if subtask.is_pending():
                next_agent = subtask.assigned_to
                return {
                    "next": next_agent,
                    "subtasks": state.subtasks,
                }

        # else route to finalizer
        return {
            "next": FINALIZER,
            "subtasks": state.subtasks,
        }

    def _create_planner_chain(self, model: IModel) -> RunnableSequence:
        self.planner_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", PLANNER_SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("system", PLANNER_STEP_INSTRUCTIONS),
            ]
        ).partial(
            kyma_agent=KYMA_AGENT, kubernetes_agent=K8S_AGENT, common_agent=COMMON
        )
        return self.planner_prompt | model.llm.with_structured_output(Plan)  # type: ignore

    async def _invoke_planner(self, state: SupervisorState) -> Plan:
        """Invoke the planner with retry logic using tenacity."""

        filtered_messages = filter_messages_via_checks(
            state.messages,
            [
                is_human_message,
                is_system_message,
                is_finalizer_message,
                is_ai_message,
            ],
        )
        reduces_messages = filter_messages(filtered_messages)

        plan: Plan = await ainvoke_chain(
            self._planner_chain,
            {
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

            # if the Planner failed to create any subtasks, raise an exception
            if not plan.subtasks:
                raise SubtasksMissingError(str(state.messages[-1].content))

            # return the plan with the subtasks to be dispatched by the Router
            return create_node_output(
                message=AIMessage(content="", name=PLANNER),
                next=ROUTER,
                subtasks=plan.subtasks,
            )
        except Exception:
            logger.exception("Error in planning")

            return create_node_output(
                message=AIMessage(
                    content="Unexpected error while processing the request. Please try again later.",
                    name=PLANNER,
                ),
                subtasks=[],  # empty subtask to make the companion response consistent
                next=END,
                error="Unexpected error while processing the request. Please try again later.",
            )

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

        # If all required agents failed: tell user that we can't give them response due to agent failure
        if state.subtasks and all(subtask.is_error() for subtask in state.subtasks):
            return {
                MESSAGES: [
                    AIMessage(
                        content="We're unable to provide a response at this time due to agent failure. "
                        "Please try again or reach out to our support team for further assistance.",
                        name=FINALIZER,
                    )
                ],
                NEXT: END,
            }

        final_response_chain = self._final_response_chain(state)

        final_response = await ainvoke_chain(
            final_response_chain,
            {"messages": state.messages},
        )
        logger.debug("Final response generated")
        return {
            MESSAGES: [
                AIMessage(
                    content=final_response.content,
                    name=FINALIZER,
                )
            ],
            NEXT: END,
        }

    async def _get_converted_final_response(
        self, state: SupervisorState
    ) -> dict[str, Any]:
        """Convert the generated final response"""
        try:
            final_response = await self._generate_final_response(state)
            logger.debug("Response conversion node started")
            return self.response_converter.convert_final_response(final_response)
        except Exception:
            logger.exception("Error in generating final response")
            return {
                MESSAGES: [
                    AIMessage(
                        content="Sorry, I encountered an error while processing the request. Try again later.",
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
        workflow.add_node(FINALIZER, self._get_converted_final_response)

        # Set the entrypoint: ENTRY --> (planner | router | finalizer)
        workflow.add_conditional_edges(
            START,
            decide_entry_point,
            {PLANNER: PLANNER, ROUTER: ROUTER, FINALIZER: FINALIZER},
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
