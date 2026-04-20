"""Provider-agnostic adapter abstraction for chat models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from gen_ai_hub.proxy.native.google_genai.clients import Client as GoogleGenAIClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from utils.logging import get_logger
from utils.models.factory import IModel, ModelPrefix

logger = get_logger(__name__)


@dataclass
class ToolCall:
    """Normalized tool call representation."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class UsageInfo:
    """Token usage information."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResponse:
    """Normalized chat response."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: UsageInfo | None = None


@runtime_checkable
class IModelAdapter(Protocol):
    """Protocol for chat model adapters."""

    async def generate(self, messages: list[dict]) -> ChatResponse:
        """Generate a response without tools."""
        ...

    async def generate_with_tools(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        """Generate a response with tool-calling capability."""
        ...


def _dicts_to_langchain_messages(
    messages: list[dict],
) -> list[SystemMessage | HumanMessage | AIMessage | ToolMessage]:
    """Convert dict messages to LangChain message objects."""
    lc_messages: list[SystemMessage | HumanMessage | AIMessage | ToolMessage] = []
    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                lc_tool_calls = [
                    {
                        "id": tc["id"],
                        "name": tc["name"],
                        "args": tc["arguments"],
                    }
                    for tc in tool_calls
                ]
                lc_messages.append(AIMessage(content=content or "", tool_calls=lc_tool_calls))
            else:
                lc_messages.append(AIMessage(content=content or ""))
        elif role == "tool":
            lc_messages.append(
                ToolMessage(
                    content=content,
                    tool_call_id=msg.get("tool_call_id", ""),
                )
            )
    return lc_messages


def _extract_usage_from_response(response: AIMessage) -> UsageInfo | None:
    """Extract usage info from LangChain AIMessage response_metadata."""
    metadata = getattr(response, "response_metadata", {}) or {}
    usage = metadata.get("token_usage") or metadata.get("usage")
    if not usage:
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata:
            return UsageInfo(
                input_tokens=getattr(usage_metadata, "input_tokens", 0),
                output_tokens=getattr(usage_metadata, "output_tokens", 0),
                total_tokens=getattr(usage_metadata, "total_tokens", 0),
            )
        return None

    if hasattr(usage, "__dict__"):
        usage = usage.__dict__

    return UsageInfo(
        input_tokens=usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )


def _normalize_tool_calls(response: AIMessage) -> list[ToolCall]:
    """Extract and normalize tool calls from a LangChain AIMessage."""
    if not response.tool_calls:
        return []
    return [
        ToolCall(
            id=tc.get("id") or "",
            name=tc.get("name", ""),
            arguments=tc.get("args", {}),
        )
        for tc in response.tool_calls
    ]


class OpenAIAdapter:
    """Wraps ChatOpenAI from SAP AI SDK."""

    def __init__(self, model: IModel, callbacks: list | None = None, metadata: dict | None = None):
        self._llm: ChatOpenAI = model.llm
        self._callbacks = callbacks or []
        self._metadata = metadata or {}

    def _make_config(self) -> dict:
        """Build RunnableConfig with callbacks and Langfuse metadata."""
        config: dict = {"callbacks": self._callbacks}
        if self._metadata:
            config["metadata"] = self._metadata
        return config

    async def generate(self, messages: list[dict]) -> ChatResponse:
        """Generate a response without tools."""
        lc_messages = _dicts_to_langchain_messages(messages)
        response: AIMessage = await self._llm.ainvoke(lc_messages, config=self._make_config())
        return ChatResponse(
            content=str(response.content) if response.content else None,
            tool_calls=_normalize_tool_calls(response),
            usage=_extract_usage_from_response(response),
        )

    async def generate_with_tools(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        """Generate a response with tool-calling capability."""
        llm_with_tools = self._llm.bind_tools(tools)
        lc_messages = _dicts_to_langchain_messages(messages)
        response: AIMessage = await llm_with_tools.ainvoke(lc_messages, config=self._make_config())
        return ChatResponse(
            content=str(response.content) if response.content else None,
            tool_calls=_normalize_tool_calls(response),
            usage=_extract_usage_from_response(response),
        )


class GeminiAdapter:
    """Wraps GoogleGenAIClient from SAP AI SDK."""

    def __init__(self, model: IModel, callbacks: list | None = None):
        self._client: GoogleGenAIClient = model.llm
        self._model_name = model.name
        self._callbacks = callbacks or []

    def _convert_messages_for_gemini(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Convert messages to Gemini format, extracting system instruction."""
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                parts: list[dict] = []
                if content:
                    parts.append({"text": content})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        parts.append(
                            {
                                "functionCall": {
                                    "name": tc["name"],
                                    "args": tc["arguments"],
                                }
                            }
                        )
                if parts:
                    contents.append({"role": "model", "parts": parts})
            elif role == "tool":
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg.get("name", ""),
                                    "response": {"result": content},
                                }
                            }
                        ],
                    }
                )
        return system_instruction, contents

    def _tools_to_gemini_format(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI-style tool definitions to Gemini function declarations."""
        declarations = []
        for tool in tools:
            func = tool.get("function", tool)
            declarations.append(
                {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                }
            )
        return [{"functionDeclarations": declarations}]

    def _parse_gemini_response(self, response: Any) -> ChatResponse:
        """Parse Gemini response into ChatResponse."""
        content = None
        tool_calls: list[ToolCall] = []
        usage = None

        if hasattr(response, "text"):
            content = response.text

        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        content = part.text
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        args = dict(fc.args) if hasattr(fc, "args") else {}
                        tool_calls.append(
                            ToolCall(
                                id=f"call_{fc.name}",
                                name=fc.name,
                                arguments=args,
                            )
                        )

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = UsageInfo(
                input_tokens=getattr(um, "prompt_token_count", 0),
                output_tokens=getattr(um, "candidates_token_count", 0),
                total_tokens=getattr(um, "total_token_count", 0),
            )

        return ChatResponse(content=content, tool_calls=tool_calls, usage=usage)

    async def generate(self, messages: list[dict]) -> ChatResponse:
        """Generate a response without tools."""
        system_instruction, contents = self._convert_messages_for_gemini(messages)
        config: dict[str, Any] = {}
        if system_instruction:
            config["system_instruction"] = system_instruction

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=contents,
            config=config,
        )
        return self._parse_gemini_response(response)

    async def generate_with_tools(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        """Generate a response with tool-calling capability."""
        system_instruction, contents = self._convert_messages_for_gemini(messages)
        gemini_tools = self._tools_to_gemini_format(tools)
        config: dict[str, Any] = {"tools": gemini_tools}
        if system_instruction:
            config["system_instruction"] = system_instruction

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=contents,
            config=config,
        )
        return self._parse_gemini_response(response)


class AnthropicAdapter:
    """Wraps Anthropic models via SAP AI SDK (ChatBedrockConverse).

    Anthropic models return content as a list of content blocks rather than
    a plain string. This adapter normalizes that into the common ChatResponse format.
    """

    def __init__(self, model: IModel, callbacks: list | None = None, metadata: dict | None = None):
        self._llm = model.llm
        self._callbacks = callbacks or []
        self._metadata = metadata or {}

    def _make_config(self) -> dict:
        """Build RunnableConfig with callbacks and Langfuse metadata."""
        config: dict = {"callbacks": self._callbacks}
        if self._metadata:
            config["metadata"] = self._metadata
        return config

    def _extract_content(self, response: AIMessage) -> str | None:
        """Extract text content from Anthropic's content block format.

        Anthropic returns content as either:
        - A plain string (simple responses)
        - A list of content blocks: [{"type": "text", "text": "..."}, {"type": "tool_use", ...}]
        """
        raw = response.content
        if isinstance(raw, str):
            return raw if raw else None
        if isinstance(raw, list):
            text_parts = []
            for block in raw:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block["text"])
                elif isinstance(block, str):
                    text_parts.append(block)
            return "\n".join(text_parts) if text_parts else None
        return str(raw) if raw else None

    async def generate(self, messages: list[dict]) -> ChatResponse:
        """Generate a response without tools."""
        lc_messages = _dicts_to_langchain_messages(messages)
        response: AIMessage = await self._llm.ainvoke(lc_messages, config=self._make_config())
        return ChatResponse(
            content=self._extract_content(response),
            tool_calls=_normalize_tool_calls(response),
            usage=_extract_usage_from_response(response),
        )

    async def generate_with_tools(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        """Generate a response with tool-calling capability."""
        llm_with_tools = self._llm.bind_tools(tools)
        lc_messages = _dicts_to_langchain_messages(messages)
        response: AIMessage = await llm_with_tools.ainvoke(lc_messages, config=self._make_config())
        return ChatResponse(
            content=self._extract_content(response),
            tool_calls=_normalize_tool_calls(response),
            usage=_extract_usage_from_response(response),
        )


def create_model_adapter(model: IModel, callbacks: list | None = None, metadata: dict | None = None) -> IModelAdapter:
    """Factory function to create the right adapter based on model name."""
    name = model.name
    if name.startswith(ModelPrefix.GPT):
        return OpenAIAdapter(model, callbacks, metadata)
    elif name.startswith(ModelPrefix.ANTHROPIC):
        return AnthropicAdapter(model, callbacks, metadata)
    elif name.startswith(ModelPrefix.GEMINI):
        return GeminiAdapter(model, callbacks)
    else:
        raise ValueError(f"Unsupported model for adapter: {name}")
