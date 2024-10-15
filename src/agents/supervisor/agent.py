import json
from typing import Any, Dict, Literal, Protocol  # noqa UP

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import RunnableSequence
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph

from agents.common.constants import (
    FINALIZER,
    MESSAGES,
    NEXT,
    PLANNER,
    SUBTASKS,
)
from agents.common.state import AgentState, Plan
from agents.common.utils import create_node_output, filter_messages, next_step
from agents.prompts import FINALIZER_PROMPT, PLANNER_PROMPT
from agents.supervisor.prompts import SUPERVISOR_ROLE_PROMPT, SUPERVISOR_TASK_PROMPT
from agents.supervisor.state import SupervisorState
from utils.logging import get_logger
from utils.models import IModel

SUPERVISOR = "Supervisor"
ROUTER = "Router"

logger = get_logger(__name__)


def next_step(state: SupervisorState) -> Literal[END, FINALIZER, ROUTER]:  # type: ignore
    """Return EXIT if next is EXIT or there is an error, FINALIZER if the next node is FINALIZER, else ROUTER."""
    if state.next == END:
        logger.debug("Ending the workflow.")
        return END
    # if there is a recoverable error
    if state.error:
        logger.error(f"Exiting the workflow due to the error: {state.error}")
        return END
    if state.next == FINALIZER:
        return FINALIZER
    return ROUTER


class SupervisorAgent:
    """Supervisor agent class."""

    model: IModel
    _name: str = SUPERVISOR
    members: list[str] = []
    plan_parser = PydanticOutputParser(pydantic_object=Plan)

    def __init__(self, model: IModel, members: list[str]):
        self.model = model
        self.members = []
        self.options = members
        self.parser = self._route_create_parser()
        self.supervisor_chain = self._create_supervisor_chain(model)
        self._planner_chain = self._create_planner_chain(model)
        self._graph = self._build_graph()

    def _route_create_parser(self) -> PydanticOutputParser:
        class RouteResponse(BaseModel):
            next: Literal[*self.options] | None = Field(  # type: ignore
                description="next agent to be called"
            )

        return PydanticOutputParser(pydantic_object=RouteResponse)

    def _create_supervisor_chain(self, model: IModel) -> RunnableSequence:
        supervisor_system_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SUPERVISOR_ROLE_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("assistant", "Subtasks: {subtasks}"),
                ("system", SUPERVISOR_TASK_PROMPT),
            ]
        ).partial(
            options=str(self.options),
            members=", ".join(self.options),
            end=str(END),
            output_format=self.parser.get_format_instructions(),
        )

        return supervisor_system_prompt | model.llm  # type: ignore

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self) -> CompiledGraph:
        """Get Supervisor agent node function."""
        return self._graph

    def _route(self, state: AgentState) -> dict[str, Any]:
        """Supervisor node."""
        try:
            result = self.supervisor_chain.invoke(
                input={
                    "messages": filter_messages(state.messages),
                    "subtasks": json.dumps(
                        [subtask.__dict__ for subtask in state.subtasks]
                    ),
                },
            )
            route_result = self.parser.parse(result.content)
            return {
                "next": route_result.next,
                "subtasks": state.subtasks,
                "messages": [AIMessage(content=result.content, name=self.name)],
            }
        except Exception as e:
            logger.exception("Error occurred in Supervisor agent.")
            return {
                MESSAGES: [
                    AIMessage(
                        content=f"Sorry, I encountered an error while processing the request. Error: {e}",
                        name=ROUTER,
                    )
                ]
            }

    def _create_planner_chain(self, model: IModel) -> RunnableSequence:
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

    def _invoke_planner(self, state: SupervisorState) -> AIMessage:
        """Invoke the planner."""
        response: AIMessage = self._planner_chain.invoke(
            input={
                "messages": filter_messages(state.messages),
            },
        )
        return response

    def _plan(self, state: SupervisorState) -> dict[str, Any]:
        """
        Breaks down the given user query into sub-tasks if the query is related to Kyma and K8s.
        If the query is general, it returns the response directly.
        """
        state.error = None

        if state.subtasks and all(subtask.completed() for subtask in state.subtasks):
            logger.debug("Finalizing as all subtasks are completed.")
            return {
                MESSAGES: state.messages,
                NEXT: FINALIZER,
            }
        elif state.subtasks:  # subtasks exist but not all are completed
            logger.debug("No need to plan as subtasks are already created.")
            return {
                MESSAGES: state.messages,
                NEXT: ROUTER,
                SUBTASKS: state.subtasks,
            }

        try:
            plan_response = self._invoke_planner(
                state,  # last message is the user query
            )
            response_content: str = plan_response.content  # type: ignore

            try:
                plan = self.plan_parser.parse(response_content)
                if plan.response:
                    return create_node_output(
                        message=AIMessage(content=plan.response, name=PLANNER),
                        next=END,
                    )
            except OutputParserException as ope:
                logger.debug(f"Problem in parsing the planner response: {ope}")
                # If 'response' field of the content of plan_response is missing due to LLM inconsistency,
                # the response is read from the plan_response content.
                return create_node_output(
                    message=AIMessage(content=response_content, name=PLANNER),
                    next=END,
                )

            if not plan.subtasks:
                raise Exception(
                    f"No subtasks are created for the given query: {state.messages[-1].content}"
                )

            return create_node_output(
                message=AIMessage(
                    content=response_content,
                    name=PLANNER,
                ),
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
                MessagesPlaceholder(variable_name="messages"),
                ("system", FINALIZER_PROMPT),
            ]
        ).partial(members=", ".join(self.members), query=last_human_message)
        return prompt | self.model.llm  # type: ignore

    def _generate_final_response(self, state: SupervisorState) -> dict[str, Any]:
        """Generate the final response."""

        final_response_chain = self._final_response_chain(state)

        try:
            final_response = final_response_chain.invoke(
                {"messages": filter_messages(state.messages)},
            ).content

            return {
                MESSAGES: [
                    AIMessage(
                        content=final_response,
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

        # Set the entrypoint: ENTRY --> planner
        workflow.set_entry_point(PLANNER)

        # Define the edge: planner --> (router | finalizer | end)
        workflow.add_conditional_edges(
            PLANNER,
            next_step,
            {ROUTER: ROUTER, FINALIZER: FINALIZER, END: END},
        )
        # Define the edge: finalizer --> end
        workflow.add_edge(FINALIZER, END)

        return workflow.compile()
