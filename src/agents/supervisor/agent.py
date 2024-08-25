import json
from typing import Any, Dict, Literal, Protocol  # noqa UP

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agents.common.state import AgentState, Plan
from agents.common.utils import filter_messages
from agents.k8s.agent import K8S_AGENT
from agents.kyma.agent import KYMA_AGENT
from utils.logging import get_logger
from utils.models import Model

PLANNER = "Planner"
SUPERVISOR = "Supervisor"
FINALIZER = "Finalize"

logger = get_logger(__name__)


class SupervisorAgent:
    """Supervisor agent class."""

    model: Model
    tools = None
    members = [KYMA_AGENT, K8S_AGENT]
    _name: str = SUPERVISOR
    parser = PydanticOutputParser(pydantic_object=Plan)  # type: ignore

    def __init__(self, model: Model, tools: list | None = None):
        self.model = model
        self.tools = tools

        options: list[str] = [FINALIZER] + self.members
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
                    "next": {"type": "string", "enum": options},
                },
                "required": ["subtasks", "next"],
            },
        }

        supervisor_system_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a supervisor tasked with managing a conversation between the agents: {members}.\n"
                    "Given the subtasks and messages, supervise conversation between the agents to a achieve "
                    "the goal. Check the subtask statuses to decide who should act next."
                    "You also decide when the work should be finalized. When all the subtasks are completed, "
                    f"respond with {FINALIZER}. ",
                ),
                MessagesPlaceholder(variable_name="messages"),
                ("system", "subtasks: {subtasks}"),
                (
                    "system",
                    "Given the messages, subtasks and subtasks statuses above, who should act next? "
                    "Or should we finalize? Select one of: {options}\n"
                    f"Set {FINALIZER} if only if all the subtasks statuses are 'completed'.",
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

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self):  # noqa ANN
        """Get Supervisor agent node function."""

        def supervisor_node(state: AgentState) -> dict[str, Any]:
            """Supervisor node."""
            try:
                result = self.supervisor_chain.invoke(
                    {
                        "messages": filter_messages(state.messages),
                        "subtasks": json.dumps(
                            [subtask.dict() for subtask in state.subtasks]
                        ),
                    }
                )
                return {
                    "next": result["next"],
                    "subtasks": state.subtasks,
                }
            except Exception as e:
                logger.exception("Error occurred in Supervisor agent.")
                return {
                    "next": None,
                    "subtasks": state.subtasks,
                    "error": str(e),
                }

        return supervisor_node
