import functools
import operator
import os
from collections.abc import Hashable, Sequence
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv
from langchain.agents import (
    AgentExecutor,
    OpenAIFunctionsAgent,
)
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI
from langfuse.callback import CallbackHandler
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from utils.models import ModelFactory

load_dotenv()

langfuse_handler = CallbackHandler(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

tavily_tool = TavilySearchResults(max_results=5)

# This executes code locally, which can be unsafe
python_repl_tool = PythonREPLTool()


def create_agent(llm: ChatOpenAI, tools: list, system_prompt: str) -> AgentExecutor:
    """Create an AI agent."""
    agent = OpenAIFunctionsAgent.from_llm_and_tools(
        llm,
        tools,
        extra_prompt_messages=[
            # MessagesPlaceholder(variable_name="messages"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ],
        system_message=SystemMessage(content=system_prompt),
    )
    # agent: BaseSingleActionAgent = create_openai_tools_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools)
    return executor


members = ["Researcher", "Coder"]

options: list[str] = ["FINISH"] + members
supervisor_prompt = (
    "You are a supervisor tasked with managing a conversation between the"
    " following agents: {members}. Given the subtasks, assign each subtask to an appropriate agent,"
    " and supervise conversation between the agents to a achieve the goal given in the query."
    " You also decide when the work is finished. When all subtasks are completed, respond with FINISH."
)

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
        ("system", supervisor_prompt),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            "Given the conversation above, who should act next?"
            " Or should we FINISH? Select one of: {options}",
        ),
    ]
).partial(options=str(options), members=", ".join(options))

model_factory = ModelFactory()
llm = model_factory.create_model("gpt-4o").llm

supervisor_chain = (
    supervisor_system_prompt
    | llm.bind_functions(functions=[function_def], function_call="assign_and_route")
    | JsonOutputFunctionsParser()
)


class Plan(BaseModel):
    """Plan to follow in future"""

    steps: list[str] = Field(
        description="different steps to follow, should be in sorted order"
    )


class AgentState(TypedDict):
    """Agent state."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str
    subtasks: list[dict[str, str]]
    current_subtask_index: int


def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Supervisor node."""

    plan_existed = False
    if not state["subtasks"]:
        if state["subtasks"] is None:
            state["subtasks"] = []

        # Initial planning
        planning_prompt = ChatPromptTemplate.from_template(
            "Given the query: {query}\n"
            "Create a plan of subtasks. Each subtask should be assigned to one of these agents: "
            "Coder, Researcher\n"
            "Respond in the format: 'Task: <description> | Agent: <agent_name>'"
        )
        plan_response = llm(planning_prompt.format_messages(query=state))

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
        plan_existed = True

    # if state["current_subtask_index"] is None set it to 0
    if state["current_subtask_index"] is None:
        state["current_subtask_index"] = 0

    # given the plan (subtasks), route the subtasks to the appropriate agents
    result = supervisor_chain.invoke(state)

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
            if not plan_existed
            else []
        ),
    }


def agent_node(state: AgentState, agent: AgentExecutor, name: str) -> dict[str, Any]:
    """Agent node."""
    current_subtask = state["subtasks"][state["current_subtask_index"]]
    if current_subtask["assigned_to"] == name:
        # TODO: add messages next to input for agent invocation
        result = agent.invoke({"input": current_subtask["description"]})
        return {
            "messages": [AIMessage(content=result["output"], name=name)],
            "current_subtask_index": state["current_subtask_index"] + 1,
        }
    else:
        return {"messages": []}


research_agent = create_agent(llm, [tavily_tool], "You are a web researcher.")
research_node = functools.partial(agent_node, agent=research_agent, name="Researcher")

code_agent = create_agent(
    llm,
    [python_repl_tool],
    "You may generate safe python code to analyze data and generate charts using matplotlib.",
)
code_node = functools.partial(agent_node, agent=code_agent, name="Coder")

workflow = StateGraph(AgentState)
workflow.add_node("Researcher", research_node)
workflow.add_node("Coder", code_node)
workflow.add_node("supervisor", supervisor_node)

for member in members:
    # We want our workers to ALWAYS "report back" to the supervisor when done
    workflow.add_edge(member, "supervisor")
# The supervisor populates the "next" field in the graph state
# which routes to a node or finishes
conditional_map: dict[Hashable, str] = {k: k for k in members}
conditional_map["FINISH"] = END
workflow.add_conditional_edges("supervisor", lambda x: x["next"], conditional_map)
# Finally, add entrypoint
workflow.add_edge(START, "supervisor")

graph = workflow.compile()

for s in graph.stream(
    {
        "messages": [
            HumanMessage(
                content="Research what is DCF in financial analysis and write python code for it."
            )
        ]
    },
    {"recursion_limit": 100, "callbacks": [langfuse_handler]},
):
    if "__end__" not in s:
        print(s)
        print("----")
