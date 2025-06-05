from typing import cast

from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from agents.common.agent import BaseAgent
from agents.common.constants import (
    AGENT_MESSAGES,
    GRAPH_STEP_TIMEOUT_SECONDS,
    KYMA_AGENT,
)
from agents.kyma.prompts import KYMA_AGENT_INSTRUCTIONS, KYMA_AGENT_PROMPT
from agents.kyma.state import KymaAgentState
from agents.kyma.tools.query import kyma_query_tool
from agents.kyma.tools.search import SearchKymaDocTool
from utils.models.factory import IModel
from utils.settings import MAIN_MODEL_NAME


class KymaAgent(BaseAgent):
    """Kyma agent specialized in handling Kyma-related queries and operations.

    This agent is equipped with tools for searching Kyma documentation and querying
    Kyma cluster resources. It uses GPT-4 for processing queries and generating responses.
    """

    def __init__(self, models: dict[str, IModel | Embeddings]) -> None:
        """Initialize the KymaAgent with necessary tools and models."""
        tools: list[BaseTool] = [
            SearchKymaDocTool(models),
            kyma_query_tool,
        ]
        agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", KYMA_AGENT_PROMPT),
                MessagesPlaceholder(variable_name=AGENT_MESSAGES),
                ("human", "{query}"),
                ("system", KYMA_AGENT_INSTRUCTIONS),
            ]
        ).partial(
            kyma_query_tool=kyma_query_tool.name,
            search_kyma_doc=SearchKymaDocTool(models).name,
        )
        super().__init__(
            name=KYMA_AGENT,
            model=cast(IModel, models[MAIN_MODEL_NAME]),
            tools=tools,
            agent_prompt=agent_prompt,
            state_class=KymaAgentState,
        )
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS
