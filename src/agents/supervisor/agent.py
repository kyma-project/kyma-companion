import json
from typing import Any, Dict, Literal, Protocol  # noqa UP

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import RunnableSequence

from agents.common.constants import EXIT, FINALIZER
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
        self.options = [FINALIZER] + members
        self.parser = self._create_parser()
        self.supervisor_chain = self._create_supervisor_chain()

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

        return supervisor_system_prompt | self.model.llm

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
                }
            except Exception as e:
                logger.exception("Error occurred in Supervisor agent.")
                return {
                    "error": str(e),
                    "next": EXIT,
                }

        return supervisor_node
