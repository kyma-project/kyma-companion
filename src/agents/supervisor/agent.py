import json
from collections.abc import Hashable
from typing import Any, Dict, Literal, Protocol  # noqa UP

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import RunnableSequence
from agents.prompts import FINALIZER_PROMPT, PLANNER_PROMPT
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.constants import END

from agents.common.constants import (
    COMMON,
    CONTINUE,
    ERROR,
    EXIT,
    FINAL_RESPONSE,
    MESSAGES,
    NEXT,
    PLANNER,
    FINALIZER,
    SUPERVISOR
)
from agents.k8s.agent import KubernetesAgent
from agents.kyma.agent import KymaAgent
from agents.common.state import AgentState, Plan
from agents.common.utils import create_node_output, filter_messages, CustomJSONEncoder
from agents.supervisor.utils import planner_edge
from agents.supervisor.prompts import SUPERVISOR_ROLE_PROMPT, SUPERVISOR_TASK_PROMPT
from utils.logging import get_logger
from utils.models import IModel

logger = get_logger(__name__)


class SupervisorAgent:
    """Supervisor agent class."""

    model: IModel
    _name: str = SUPERVISOR
    graph: CompiledGraph
    members: list[str] = []

    plan_parser = PydanticOutputParser(pydantic_object=Plan)  # type: ignore

    def __init__(self, model: IModel, members: list[str]):
        self.model = model
        self.options = [FINALIZER] + members
        self.parser = self._create_parser()
        self.supervisor_chain = self._create_supervisor_chain()
        self.kyma_agent = KymaAgent(model)
        self.k8s_agent = KubernetesAgent(model)
        self.members = [self.kyma_agent.name, self.k8s_agent.name, COMMON]
        self.graph = self._build_graph()

    def _create_parser(self) -> PydanticOutputParser:
        class RouteResponse(BaseModel):
            next: Literal[*self.options] | None = Field(  # type: ignore
                description="next agent to be called"
            )

        return PydanticOutputParser(pydantic_object=RouteResponse)

    def _create_supervisor_chain(self) -> RunnableSequence:
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
            finalizer=FINALIZER,
            output_format=self.parser.get_format_instructions(),
        )

        return supervisor_system_prompt | self.model.llm  # type: ignore

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self) -> CompiledGraph:
        """Get Supervisor agent node function."""
        return self.graph

    def _supervisor_node(self, state: AgentState) -> dict[str, Any]:
        """Supervisor node."""
        try:
            result = self.supervisor_chain.invoke(
                input={
                    "messages": filter_messages(state.messages),
                    "subtasks": json.dumps(
                        [subtask.dict() for subtask in state.subtasks]
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
                "error": str(e),
                "next": EXIT,
            }

    def _final_response_chain(self, state: AgentState) -> RunnableSequence:
        prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                ("system", FINALIZER_PROMPT),
            ]
        ).partial(members=", ".join(self.members), query=state.input.query)
        return prompt | self.model.llm  # type: ignore

    def _finalizer_node(self, state: AgentState) -> dict[str, Any]:
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

    def _planner_node(self, state: AgentState) -> dict[str, Any]:
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

    def _build_graph(self) -> CompiledGraph:
        # Define a new graph.
        workflow = StateGraph(AgentState)

        # Define the nodes of the graph.
        workflow.add_node("router", self._supervisor_node)
        workflow.add_node("finalizer", self._finalizer_node)
        workflow.add_node("planner", self._planner_node)

        # Set the entrypoint: ENTRY --> planner
        workflow.set_entry_point("planner")

        # Define the edge: planner --> (router | end)
        workflow.add_conditional_edges("planner", planner_edge)

        # Define the edge: router --> (kymaAgent | k8sAgnt | common | finalizer | end)
        for member in self.members:
            # We want our workers to ALWAYS "report back" to the supervisor when done
            workflow.add_edge(member, "router")
        # The supervisor populates the "next" field in the graph state
        # which routes to a node or finishes
        conditional_map: dict[Hashable, str] = {
            k: k for k in self.members + [FINALIZER, EXIT]
        }
        workflow.add_conditional_edges(SUPERVISOR, lambda x: x.next, conditional_map)

        # Define the edge: finalizer --> exit
        workflow.add_edge("finalizer", EXIT)

        # Define the edge: exit --> end
        workflow.add_edge(EXIT, "__end__")

        return workflow.compile()
