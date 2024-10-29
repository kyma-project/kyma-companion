from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import ToolNode

from agents.common.state import SubTaskStatus
from utils.models import IModel


class BaseAgent:
    """Base agent class with common functionality."""
    
    def __init__(self, name: str, model: IModel, tools: list[Any], system_prompt: str):
        self._name = name
        self.model = model
        self.tools = tools
        self.chain = self._create_chain(system_prompt)
        self.graph = self._build_graph()
        
    @property
    def name(self) -> str:
        return self._name

    def agent_node(self) -> CompiledGraph:
        return self.graph

    def _create_chain(self, system_prompt: str) -> Any:
        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "query: {query}"),
        ])
        return agent_prompt | self.model.llm.bind_tools(self.tools)

    def is_internal_message(self, message: BaseMessage) -> bool:
        if (message.additional_kwargs is not None 
            and "owner" in message.additional_kwargs
            and message.additional_kwargs["owner"] == self.name
            and message.tool_calls):  # type: ignore
            return True

        tool_names = [tool.name for tool in self.tools]
        if isinstance(message, ToolMessage) and message.name in tool_names:
            return True
        return False

    def _subtask_selector_node(self, state: Any) -> dict[str, Any]:
        """Generic subtask selector implementation."""
        if state.k8s_client is None:
            raise ValueError("Kubernetes client is not initialized.")
            
        for subtask in state.subtasks:
            if (subtask.assigned_to == self.name 
                and subtask.status != SubTaskStatus.COMPLETED):
                return {"my_task": subtask}

        return {
            "is_last_step": True,
            "messages": [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=self.name,
                )
            ],
        }

    def _model_node(self, state: Any, config: RunnableConfig) -> dict[str, Any]:
        """Generic model node implementation."""
        inputs = {
            "messages": state.messages,
            "query": state.my_task.description,
        }

        try:
            response = self.chain.invoke(inputs, config)
        except Exception as e:
            return {
                "messages": [
                    AIMessage(
                        content=f"Sorry, I encountered an error: {e}",
                        name=self.name,
                    )
                ]
            }

        if (state.is_last_step 
            and isinstance(response, AIMessage)
            and response.tool_calls):
            return {
                "messages": [
                    AIMessage(
                        content=f"Sorry, the {self.name} needs more steps.",
                        name=self.name,
                    )
                ]
            }

        response.additional_kwargs["owner"] = self.name
        return {"messages": [response]}

    def _finalizer_node(self, state: Any, config: RunnableConfig) -> dict[str, Any]:
        state.my_task.complete()
        return {
            "messages": [
                AIMessage(id=m.id)  # type: ignore
                for m in state.messages
                if self.is_internal_message(m)
            ],
            "my_task": None,
        }

    def _build_graph(self) -> CompiledGraph:
        workflow = StateGraph(type(self).__name__ + "State")
        
        workflow.add_node("subtask_selector", self._subtask_selector_node)
        workflow.add_node("agent", self._model_node)
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.add_node("finalizer", self._finalizer_node)

        workflow.set_entry_point("subtask_selector")
        workflow.add_conditional_edges(
            "subtask_selector", 
            lambda s: "agent" if not s.is_last_step else "__end__"
        )
        workflow.add_conditional_edges(
            "agent",
            lambda s: "tools" if isinstance(s.messages[-1], AIMessage) and s.messages[-1].tool_calls else "finalizer"
        )
        workflow.add_edge("tools", "agent")
        workflow.add_edge("finalizer", "__end__")

        return workflow.compile() 