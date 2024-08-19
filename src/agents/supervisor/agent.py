import os
from collections.abc import AsyncGenerator, Hashable
from typing import Any, Literal, Protocol

from langchain.agents import AgentExecutor
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langfuse.callback import CallbackHandler
from langgraph.checkpoint import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph.graph import CompiledGraph
from pydantic import BaseModel

from agents.common.utils import AgentState
from agents.k8s.agent import K8S_AGENT_NAME, k8s_agent_node
from agents.kyma.agent import KYMA_AGENT_NAME, kyma_agent_node
from utils.logging import get_logger
from utils.models import Model

SUPERVISOR_NAME = "Supervisor"

logger = get_logger(__name__)

langfuse_handler = CallbackHandler(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)


class Message(BaseModel):
    """Message data model."""

    input: str


def should_continue(state: MessagesState) -> Literal["action", "__end__"]:
    """Return the next node to execute."""
    last_message = state["messages"][-1]
    return "action" if last_message.tool_calls else "__end__"


def filter_messages(messages: list) -> list:
    """This is very simple helper function which only ever uses the last four messages"""
    return messages[-10:]


def agent_node(
    state: dict[str, Any], agent: AgentExecutor, name: str
) -> dict[str, Any]:
    """It filters the messages and invokes the agent."""
    state["messages"] = filter_messages(state["messages"])

    result = agent.invoke(state)
    return {"messages": [HumanMessage(content=result["output"], name=name)]}


class Agent(Protocol):
    """Agent interface."""

    async def astream(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[dict, None]:
        """Stream the input to the supervisor asynchronously."""
        ...


class SupervisorAgent:
    """Supervisor agent class."""

    model: Model
    memory: BaseCheckpointSaver
    kyma_agent = None
    tools = None
    members = [KYMA_AGENT_NAME, K8S_AGENT_NAME]

    def __init__(self, model: Model, memory: BaseCheckpointSaver):
        self.model = model
        self.memory = memory

        options: list[str] = ["FINISH"] + self.members
        function_def = {
            "name": "assign_and_route",
            "description": "Assign subtasks to agents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subtasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "assigned_to": {"enum": options},
                            },
                            "required": ["description", "assigned_to"],
                        },
                    },
                    "next": {"type": "string", "enum": ["FINISH"] + options},
                },
                "required": ["subtasks", "next"],
            },
        }

        supervisor_system_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a supervisor tasked with managing a conversation between the"
                    " following agents: {members}. Given the subtasks, assign each subtask to an appropriate agent,"
                    " and supervise conversation between the agents to a achieve the goal given in the query."
                    " You also decide when the work is finished. When all subtasks are completed, respond with FINISH.",
                ),
                MessagesPlaceholder(variable_name="messages"),
                (
                    "system",
                    "Given the conversation above, who should act next?"
                    " Or should we FINISH? Select one of: {options}",
                ),
            ]
        ).partial(options=str(options), members=", ".join(options))

        self.supervisor_chain = (
            supervisor_system_prompt
            | model.llm.bind_functions(
                functions=[function_def], function_call="assign_and_route"
            )
            | JsonOutputFunctionsParser()
        )

        self.graph = self._build_graph()

    def _plan(self, state: MessagesState) -> MessagesState:
        """Breaks down the given user query into sub-tasks."""
        # TODO: implement this method
        return state

    def _route(self, state: MessagesState) -> MessagesState:
        """Route the each sub-task to the appropriate agent."""
        # TODO: Implement the logic to route each sub-task to the appropriate agent.
        return state

    def supervisor_node(self, state: AgentState) -> dict[str, Any]:
        """Supervisor node."""

        if state["current_subtask_index"] is None:
            state["current_subtask_index"] = 0

        first_supervisor_call = False
        if state["current_subtask_index"] == 0:
            if state["subtasks"] is None:
                state["subtasks"] = []

            # Initial planning
            planning_prompt = ChatPromptTemplate.from_template(
                "Given the query: {query}\n"
                "Create a plan of subtasks. Each subtask should be assigned to one of these agents: "
                "{members}\n"
                "Respond in the format: 'Task: <description> | Agent: <agent_name>'"
            ).partial(members=", ".join(self.members))
            plan_response = self.model.llm(planning_prompt.format_messages(query=state))

            for line in plan_response.content.split("\n"):
                if line.strip():
                    task, agent = line.split("|")
                    state["subtasks"].append(
                        {
                            "description": task.split(":")[1].strip(),
                            "assigned_to": agent.split(":")[1].strip(),
                        }
                    )
        else:
            first_supervisor_call = True

        # given the plan (subtasks), route the subtasks to the appropriate agents
        result = self.supervisor_chain.invoke(state)

        return {
            "next": result["next"],
            "subtasks": state["subtasks"],
            "current_subtask_index": state["current_subtask_index"],
            "messages": (
                [
                    AIMessage(
                        content=f"Task decomposed into subtasks and assigned to agents: {state['subtasks']}",
                        name="Supervisor",
                    )
                ]
                if not first_supervisor_call
                else []
            ),
        }

    def _build_graph(self) -> CompiledGraph:
        """Create a supervisor agent."""

        workflow = StateGraph(AgentState)
        workflow.add_node(KYMA_AGENT_NAME, kyma_agent_node)
        workflow.add_node(K8S_AGENT_NAME, k8s_agent_node)
        workflow.add_node(SUPERVISOR_NAME, self.supervisor_node)

        for member in self.members:
            # We want our workers to ALWAYS "report back" to the supervisor when done
            workflow.add_edge(member, SUPERVISOR_NAME)
        # The supervisor populates the "next" field in the graph state
        # which routes to a node or finishes
        conditional_map: dict[Hashable, str] = {k: k for k in self.members}
        conditional_map["FINISH"] = END
        workflow.add_conditional_edges(
            SUPERVISOR_NAME, lambda x: x["next"], conditional_map
        )
        # Finally, add entrypoint
        workflow.add_edge(START, SUPERVISOR_NAME)

        graph = workflow.compile(checkpointer=self.memory)
        return graph

    async def astream(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[dict, None]:
        """Stream the input to the supervisor asynchronously."""
        async for chunk in self.graph.astream(
            input={"messages": [HumanMessage(content=message.input)]},
            config={
                "configurable": {"thread_id": conversation_id},
                "callbacks": [langfuse_handler],
            },
        ):
            if "__end__" not in chunk:
                yield chunk
