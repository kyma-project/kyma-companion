import json
from agents.tools.kyma_resources_tool import KYMA_RESOURCES_TOOL_NAME
import re
from agents.tools.agent_tools import (create_kubernetes_extraction_tool, create_kyma_documentation_extraction_tool,
                                      create_btp_kyma_documentation_extraction_tool, KUBERNETES_TOOL_NAME,
                                      KYMA_OS_TOOL_NAME, KYMA_BTP_TOOL_NAME)
from agents.tools.kyma_resources_tool import create_kyma_resources_extraction_tool
from .prompt_templates import REACT_AGENT_PROMPT_TEMPLATE
from helpers.models import (create_model, LLM_AZURE_GPT4_32K_STREAMING)
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain.prompts import PromptTemplate
from clients.multimodel_client import MultiModelClient


def replace_quotes(sentence):
    parts = sentence.split("```")
    modified_parts = []

    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Preserve quotes within words like "It's", "we've", etc and replace the rest
            part = re.sub(r"(?<![a-zA-Z0-9])'|'(?![a-zA-Z0-9])", "`", part)
            part = re.sub(r'(?<![a-zA-Z0-9])"|"(?![a-zA-Z0-9])', "`", part)
            modified_parts.append(part)
        else:
            # Preserve the quotes within code blocks
            modified_parts.append(part)

    modified_sentence = "```".join(modified_parts)

    return modified_sentence


def generate_kubernetes_tool_message(tool_input):
    message = "Extracting cluster resources"
    try:
        command = tool_input.split(" ")
        message += ": "
        if "get" in command:
            message += "getting " + command[command.index("get") + 1] + " "
        if "describe" in command:
            message += "describing " + command[command.index("describe") + 1] + ", '" + command[
                command.index("describe") + 2] + "' "
        if "-n" in command:
            message += "in '" + command[command.index("-n") + 1] + "' namespace "
    except Exception as e:
        print(e)
    return message


def generate_tool_notification(tool: str, tool_input: str) -> str:
    message = ""
    if tool == KUBERNETES_TOOL_NAME:
        message = "Retrieving Kubernetes native resource"
    if tool == KYMA_RESOURCES_TOOL_NAME:
        message = "Retrieving Kyma resources"
    if tool == KYMA_OS_TOOL_NAME:
        message = "Searching OS Kyma documentation"
    if tool == KYMA_BTP_TOOL_NAME:
        message = "Searching BTP Kyma documentation"
    return message


def generate_streaming_output(chunk: dict) -> str:
    # Agent Action
    if "actions" in chunk:
        for action in chunk["actions"]:
            message = generate_tool_notification(action.tool, action.tool_input)
            return json.dumps({"step": "action", "result": message})
    # Observation
    elif "steps" in chunk:
        for step in chunk["steps"]:
            return json.dumps({"step": "processing", "result": "Analyzing the result"})
    # Final result
    elif "output" in chunk:
        return json.dumps({"step": "output", "result": replace_quotes(chunk["output"])})
    else:
        raise ValueError()


def create_assistant_agent(history: RedisChatMessageHistory, namespace: str) -> RunnableWithMessageHistory:
    llm = MultiModelClient()
    tools = [
        create_kubernetes_extraction_tool(namespace),
        create_kyma_resources_extraction_tool(namespace),
        create_kyma_documentation_extraction_tool(),
        create_btp_kyma_documentation_extraction_tool()
    ]
    agent_prompt = PromptTemplate(template=REACT_AGENT_PROMPT_TEMPLATE,
                                  input_variables=["agent_scratchpad", "input", "tools", "tool_names",
                                                   "chat_history"])
    agent_executor = AgentExecutor(agent=create_react_agent(llm, tools, agent_prompt),
                                   tools=tools, verbose=True, handle_parsing_errors=True)
    agent = RunnableWithMessageHistory(
        agent_executor,
        lambda session_id: history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )
    return agent
