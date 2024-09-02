import json
from typing import Any, Dict, Literal, Protocol  # noqa UP

from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agents.common.constants import FINALIZER
from agents.common.state import AgentState
from agents.common.utils import filter_messages
from agents.supervisor.prompts import SUPERVISOR_ROLE_PROMPT, SUPERVISOR_TASK_PROMPT
from utils.logging import get_logger
from utils.models import IModel

SUPERVISOR = "Supervisor"

logger = get_logger(__name__)


class SupervisorAgent:
    """Supervisor agent class."""

    model: IModel
    _name: str = SUPERVISOR

    def __init__(self, model: IModel, members: list[str]):
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
                ("system", SUPERVISOR_ROLE_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("assistant", "Subtasks: {subtasks}"),
                ("system", SUPERVISOR_TASK_PROMPT),
            ]
        ).partial(options=str(options), members=", ".join(options), finalizer=FINALIZER)

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
