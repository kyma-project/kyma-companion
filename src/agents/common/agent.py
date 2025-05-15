from typing import Any, Literal, Protocol

from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agents.common.chunk_summarizer import ToolResponseSummarizer
from agents.common.constants import (
    AGENT_MESSAGES,
    AGENT_MESSAGES_SUMMARY,
    CONTINUE,
    ERROR,
    IS_LAST_STEP,
    MESSAGES,
    MY_TASK,
    SUBTASKS,
    SUMMARIZATION,
    TOOL_RESPONSE_TOKEN_COUNT_LIMIT,
    TOOLS_NEXT_STEP,
    TOTAL_CHUNKS_LIMIT,
)
from agents.common.state import BaseAgentState, SubTaskStatus
from agents.common.utils import (
    compute_string_token_count,
    convert_string_to_object,
    filter_messages,
    filter_valid_messages,
    should_continue,
)
from agents.summarization.summarization import MessageSummarizer
from utils.chain import ainvoke_chain
from utils.logging import get_logger
from utils.models.factory import IModel, ModelType
from utils.settings import (
    SUMMARIZATION_TOKEN_LOWER_LIMIT,
    SUMMARIZATION_TOKEN_UPPER_LIMIT,
)

logger = get_logger(__name__)

# as default recursive limit is 25 and the graph has 3 nodes
# the latest call must withing the nodes (steps) number
AGENT_STEPS_NUMBER = 3


def subtask_selector_edge(state: BaseAgentState) -> Literal["agent", "finalizer"]:
    """Function that determines whether to finalize or call agent."""
    if state.is_last_step and state.my_task is None:
        return "finalizer"
    return "agent"


def agent_edge(state: BaseAgentState) -> Literal["Summarization", "finalizer"]:
    """Function that determines whether to call tools or finalizer."""
    last_message = state.agent_messages[-1]
    if isinstance(last_message, AIMessage) and not last_message.tool_calls:
        return "finalizer"
    return "Summarization"  # from SUMMARIZATION --> tools


class IAgent(Protocol):
    """Agent interface."""

    def agent_node(self):  # noqa ANN
        """Main agent function."""
        ...

    @property
    def name(self) -> str:
        """Agent name."""
        ...


class BaseAgent:
    """Abstract base agent class."""

    def __init__(
        self,
        name: str,
        model: IModel | Embeddings,
        tools: list,
        agent_prompt: ChatPromptTemplate,
        state_class: type,
    ):
        self._name = name
        self.model = model
        self.tools = tools
        self.summarization = MessageSummarizer(
            model=model,
            tokenizer_model_type=ModelType(model.name),
            token_lower_limit=SUMMARIZATION_TOKEN_LOWER_LIMIT,
            token_upper_limit=SUMMARIZATION_TOKEN_UPPER_LIMIT,
            messages_key=AGENT_MESSAGES,
            messages_summary_key=AGENT_MESSAGES_SUMMARY,
        )
        self.tool_response_summarization = ToolResponseSummarizer(model=model)
        self.chain = self._create_chain(agent_prompt)
        self.graph = self._build_graph(state_class)
        self.graph.step_timeout = 60  # Default timeout, can be overridden

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self) -> Any:
        """Get agent node function."""
        return self.graph

    def _create_chain(self, agent_prompt: ChatPromptTemplate) -> Any:
        return agent_prompt | self.model.llm.bind_tools(self.tools)

    def _subtask_selector_node(self, state: BaseAgentState) -> dict[str, Any]:
        if state.k8s_client is None:
            raise ValueError("Kubernetes client is not initialized.")

        # find subtasks assigned to this agent and not completed.
        for subtask in state.subtasks:
            if (
                subtask.assigned_to == self.name
                and subtask.status == SubTaskStatus.PENDING
            ):
                return {
                    MY_TASK: subtask,
                }

        return {
            AGENT_MESSAGES: [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=self.name,
                )
            ],
            IS_LAST_STEP: True,
        }

    async def _invoke_chain(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        input_messages = state.get_agent_messages_including_summary()
        if len(state.agent_messages) == 0:
            input_messages = filter_messages(state.messages)

        # invoke the chain.
        response = await ainvoke_chain(
            self.chain,
            {
                AGENT_MESSAGES: filter_valid_messages(input_messages),
                "query": state.my_task.description,
            },
            config=config,
        )
        return response

    async def _summarize_tool_response(
        self, state: BaseAgentState, config: RunnableConfig
    ) -> str:
        tool_response = []
        for message in reversed(state.agent_messages):
            if isinstance(message, ToolMessage):
                # convert string into object
                tool_response_object = convert_string_to_object(str(message.content))
                if isinstance(tool_response_object, list):
                    tool_response.extend(tool_response_object)
                else:
                    tool_response.append(tool_response_object)
            else:
                break
        response = ""
        token_count = compute_string_token_count(
            str(tool_response), ModelType(self.model.name)
        )
        logger.info(f"Tool Response Token count: {token_count}")
        # if token limit exceeds
        if token_count > TOOL_RESPONSE_TOKEN_COUNT_LIMIT[self.model.name]:

            nums_of_chunks = (
                token_count // TOOL_RESPONSE_TOKEN_COUNT_LIMIT[self.model.name]
            ) + 1
            logger.info(f"Number of Chunks for summarization : {nums_of_chunks}")

            if nums_of_chunks > TOTAL_CHUNKS_LIMIT:
                raise Exception("Total number of chunks exceeds TOTAL_CHUNKS_LIMIT")

            # summarize tool content
            response = await self.tool_response_summarization.summarize_tool_response(
                tool_response=tool_response,
                user_query=state.my_task.description,
                config=config,
                nums_of_chunks=nums_of_chunks,
            )

            logger.info("Tool Response Summarization completed")
            # update all tool message which is already summarized and
            # add new AI Message with summarized content
            for message in reversed(state.agent_messages):
                if isinstance(message, ToolMessage):
                    message.content = "Summarized"
                else:
                    break

        return response

    async def _summarize_tool_responses_node(
        self, state: BaseAgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        response = ""
        if state.agent_messages and isinstance(state.agent_messages[-1], ToolMessage):
            try:
                response = await self._summarize_tool_response(state, config)
            except Exception as e:
                logger.error(
                    f"Error while summarizing the tool response , Error : {e}."
                )
                return {
                    AGENT_MESSAGES: [
                        AIMessage(
                            content="Your request is too broad and requires analyzing "
                            "more resources than allowed at once. "
                            "Please specify a particular resource you'd like to analyze so "
                            "I can assist you more effectively.",
                            name=self.name,
                        )
                    ],
                    TOOLS_NEXT_STEP: "finalizer",
                }
        if response:
            return {
                AGENT_MESSAGES: [
                    AIMessage(
                        content="Summarized Tool Response - " + response,
                        name=self.name,
                    )
                ],
                TOOLS_NEXT_STEP: "agent",
            }
        return {TOOLS_NEXT_STEP: "agent"}

    async def _model_node(
        self, state: BaseAgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        try:
            if state.remaining_steps > AGENT_STEPS_NUMBER:
                response = await self._invoke_chain(state, config)
            else:
                if state.my_task:
                    state.my_task.status = SubTaskStatus.ERROR

                logger.error(
                    f"Agent reached the recursive limit, steps remaining: {state.remaining_steps}."
                )
                return {
                    AGENT_MESSAGES: [
                        AIMessage(
                            content="Agent reached the recursive limit, not able to call Tools again",
                            name=self.name,
                        )
                    ],
                }
        except Exception as e:
            error_message = "An error occurred while processing the request"
            error_message_with_trace = error_message + f": {e}"
            logger.error(error_message_with_trace)

            # Update current subtask status
            if state.my_task:
                state.my_task.status = SubTaskStatus.ERROR

            return {
                AGENT_MESSAGES: [
                    AIMessage(
                        content="Sorry, an unexpected error occurred while processing your request."
                        "Please try again later.",
                        name=self.name,
                    )
                ],
                ERROR: error_message,  # we dont send trace to frontend
            }

        # if the recursive limit is reached and the response is a tool call, return a message.
        # 'is_last_step' is a boolean that is True if the recursive limit is reached.
        if (
            state.is_last_step
            and isinstance(response, AIMessage)
            and response.tool_calls
        ):
            return {
                AGENT_MESSAGES: [
                    AIMessage(
                        content="Sorry, I need more steps to process the request.",
                        name=self.name,
                    )
                ],
            }

        response.additional_kwargs["owner"] = self.name
        return {
            AGENT_MESSAGES: [response],
        }

    def _finalizer_node(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        """Finalizer node will mark the task as completed."""
        if state.my_task is not None and state.my_task.status != SubTaskStatus.ERROR:
            logger.info("Agent task completed")
            state.my_task.complete()

        agent_pre_message = f"'{state.my_task.description}' , Agent Response - "
        # Check if agent_messages exists and has at least one element
        if (
            hasattr(state, "agent_messages")
            and state.agent_messages
            and isinstance(state.agent_messages, list)
            and len(state.agent_messages) > 0
            and state.agent_messages[-1]
            and hasattr(state.agent_messages[-1], "content")
        ):

            current_content = state.agent_messages[-1].content or ""
            state.agent_messages[-1].content = agent_pre_message + current_content

        # clean all agent messages to avoid populating the checkpoint with unnecessary messages.
        return {
            MESSAGES: [
                AIMessage(
                    content=state.agent_messages[-1].content,
                    name=self.name,
                    id=state.agent_messages[-1].id,
                )
            ],
            SUBTASKS: state.subtasks,
        }

    def _build_graph(self, state_class: type) -> Any:
        # Define a new graph
        workflow = StateGraph(state_class)

        # Define nodes with async awareness
        workflow.add_node("subtask_selector", self._subtask_selector_node)
        workflow.add_node("agent", self._model_node)
        workflow.add_node(
            "tool_response_summarization", self._summarize_tool_responses_node
        )
        workflow.add_node(
            "tools", ToolNode(tools=self.tools, messages_key=AGENT_MESSAGES)
        )
        workflow.add_node("finalizer", self._finalizer_node)
        workflow.add_node(SUMMARIZATION, self.summarization.summarization_node)

        # Set the entrypoint: ENTRY --> subtask_selector
        workflow.set_entry_point("subtask_selector")

        # Define the edge: subtask_selector --> (agent | end)
        workflow.add_conditional_edges("subtask_selector", subtask_selector_edge)

        # Define the edge: agent --> (summarization | finalizer)
        workflow.add_conditional_edges("agent", agent_edge)

        # Define the edge: tool --> tool
        workflow.add_edge("tools", "tool_response_summarization")

        workflow.add_conditional_edges(
            "tool_response_summarization",
            lambda x: x.tools_next_step,
            {"finalizer": "finalizer", "agent": "agent"},
        )

        # Define the edge: summarization --> agent | error_handler
        workflow.add_conditional_edges(
            SUMMARIZATION,
            should_continue,
            {
                CONTINUE: "tools",
                END: END,
            },
        )

        # Define the edge: finalizer --> END
        workflow.add_edge("finalizer", "__end__")

        return workflow.compile()
