import json
from typing import Any, Dict, Literal, Protocol  # noqa UP

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agents.common.state import AgentState, Plan
from agents.common.utils import filter_messages
from utils.logging import get_logger
from utils.models import Model

SUPERVISOR = "Supervisor"
COMMON = "Common"
FINALIZER = "Finalize"

logger = get_logger(__name__)


class SupervisorAgent:
    """Supervisor agent class."""

    model: Model
    _name: str = SUPERVISOR
    parser = PydanticOutputParser(pydantic_object=Plan)  # type: ignore

    def __init__(self, model: Model, members: list[str]):
        self.model = model

        options: list[str] = [FINALIZER] + members
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
                    "You are a supervisor managing a conversation between the agents: {members}.\n"
                    "Your task is to oversee the conversation to achieve the goal, checking subtasks "
                    "and their statuses to decide the next action or finalization.",
                ),
                MessagesPlaceholder(variable_name="messages"),
                ("assistant", "Subtasks and their current statuses: {subtasks}"),
                (
                    "system",
                    "1. Review and summarize the LATEST status of all subtasks.\n"
                    "2. Check if the latest subtasks have the status 'completed'.\n"
                    "3. Decide on the next action:\n"
                    f"   a) If the latest subtasks are 'completed', you MUST set {FINALIZER}.\n"
                    "   b) Otherwise, select the next agent to act from: {options}.\n"
                    "Provide your decision and a brief explanation.",
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
