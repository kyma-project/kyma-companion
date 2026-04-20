"""CompanionAgent — single tool-use loop replacing LangGraph orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import tiktoken

from agents.common.constants import ERROR_RESPONSE
from agents.common.data import Message
from agents.new_prompts import build_system_prompt
from agents.tools import ToolRegistry
from services.conversation_store import IConversationStore
from services.k8s import IK8sClient
from services.model_adapter import IModelAdapter, UsageInfo
from services.response_converter import ResponseConverter
from utils.logging import get_logger
from utils.streaming import (
    build_tasks_list,
    make_error_event,
    make_final_event,
    make_planning_event,
)

logger = get_logger(__name__)

# Maximum number of tool-call rounds to prevent infinite loops.
MAX_TOOL_ROUNDS = 10
# Token threshold for truncating conversation history.
HISTORY_TOKEN_LIMIT = 24_000


class CompanionAgent:
    """Single tool-use loop agent replacing the multi-step LangGraph pipeline.

    Flow:
        User → Load history from Redis → Build system prompt → LLM with tools
        → [tool call → execute → return result → LLM]* → Final answer → Save to Redis
    """

    def __init__(
        self,
        adapter: IModelAdapter,
        tool_registry: ToolRegistry,
        conversation_store: IConversationStore,
        response_converter: ResponseConverter | None = None,
    ):
        self._adapter = adapter
        self._tools = tool_registry
        self._store = conversation_store
        self._response_converter = response_converter
        try:
            self._encoding = tiktoken.encoding_for_model("gpt-4")
        except KeyError:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    async def handle_message(
        self,
        conversation_id: str,
        message: Message,
        k8s_client: IK8sClient,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[bytes]:
        """Handle a single user message, streaming SSE events.

        Args:
            conversation_id: Unique conversation thread ID.
            message: User message with resource context.
            k8s_client: K8s client for the current request.
            history: Pre-loaded conversation history (skips Redis read if provided).

        Yields:
            SSE event bytes.
        """
        try:
            async for chunk in self._run(conversation_id, message, k8s_client, history):
                yield chunk
        except Exception:
            logger.exception("Error in CompanionAgent.handle_message")
            yield make_error_event(ERROR_RESPONSE)

    async def _run(
        self,
        conversation_id: str,
        message: Message,
        k8s_client: IK8sClient,
        preloaded_history: list[dict] | None = None,
    ) -> AsyncGenerator[bytes]:
        """Core agent loop."""
        # 1. Load conversation history (skip if already loaded by caller)
        history = (
            preloaded_history if preloaded_history is not None else await self._store.load_messages(conversation_id)
        )

        # 2. Build system prompt — split into static + dynamic for prompt caching
        static_prompt, resource_context = build_system_prompt(
            resource_kind=message.resource_kind,
            resource_name=message.resource_name,
            resource_api_version=message.resource_api_version,
            namespace=message.namespace,
            resource_scope=message.resource_scope,
            resource_related_to=message.resource_related_to,
        )

        # 3. Truncate history if too long
        history = self._truncate_history(history)

        # 4. Build messages list
        # Static system prompt first (cacheable — identical across all requests)
        # Dynamic resource context second (varies per request, breaks cache only for itself)
        messages: list[dict] = [
            {"role": "system", "content": static_prompt},
            {"role": "system", "content": resource_context},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message.query})

        # 5. Get tool schemas
        tool_schemas = self._tools.get_tool_schemas()

        # 6. Send initial planning event
        yield make_planning_event()

        # 7. Tool-use loop
        tool_calls_made: list[dict] = []
        total_usage = UsageInfo()

        for _ in range(MAX_TOOL_ROUNDS):
            # Call LLM with tools
            response = await self._adapter.generate_with_tools(messages, tool_schemas)

            # Accumulate usage
            if response.usage:
                total_usage.input_tokens += response.usage.input_tokens
                total_usage.output_tokens += response.usage.output_tokens
                total_usage.total_tokens += response.usage.total_tokens

            # If no tool calls, we have the final answer
            if not response.tool_calls:
                final_content = response.content or ""

                # Convert YAML to HTML with resource links
                if self._response_converter:
                    final_content = await self._convert_response(final_content)

                # Build final tasks list
                tasks = build_tasks_list(tool_calls_made)

                yield make_final_event(final_content, tasks=tasks)

                # Save updated history
                history.append({"role": "user", "content": message.query})
                # Add assistant message to history
                history.append({"role": "assistant", "content": final_content})
                await self._store.save_messages(conversation_id, history)

                return

            # Execute tool calls in parallel
            # Add assistant message with tool calls to conversation
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                    for tc in response.tool_calls
                ],
            }
            messages.append(assistant_msg)

            # Execute all tool calls concurrently
            results = await asyncio.gather(
                *[self._tools.execute_tool(tc.name, tc.arguments, k8s_client) for tc in response.tool_calls]
            )

            # Append results to messages in order (must match tool_call order)
            for tc, result in zip(response.tool_calls, results, strict=True):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

                tool_calls_made.append(
                    {
                        "name": tc.name,
                        "task_title": f"Queried {tc.name}",
                        "agent": tc.name,
                    }
                )

        # If we exhausted all rounds, return what we have
        logger.warning(f"CompanionAgent exhausted {MAX_TOOL_ROUNDS} tool rounds for conversation {conversation_id}")
        # Make a final call without tools to get the response
        response = await self._adapter.generate(messages)
        final_content = response.content or "I was unable to complete the analysis within the allowed steps."

        if self._response_converter:
            final_content = await self._convert_response(final_content)

        tasks = build_tasks_list(tool_calls_made)
        yield make_final_event(final_content, tasks=tasks)

        # Save history
        history.append({"role": "user", "content": message.query})
        history.append({"role": "assistant", "content": final_content})
        await self._store.save_messages(conversation_id, history)

    def _truncate_history(self, history: list[dict]) -> list[dict]:
        """Truncate conversation history to fit within token limits.

        Keeps the most recent messages, removing oldest ones first.
        Ensures tool messages always follow their assistant messages.
        """
        if not history:
            return history

        total_tokens = sum(len(self._encoding.encode(str(msg.get("content", "")))) for msg in history)

        if total_tokens <= HISTORY_TOKEN_LIMIT:
            return history

        # Remove oldest messages until under limit
        truncated = list(history)
        while truncated and total_tokens > HISTORY_TOKEN_LIMIT:
            removed = truncated.pop(0)
            total_tokens -= len(self._encoding.encode(str(removed.get("content", ""))))
            # If we removed an assistant message with tool_calls,
            # also remove the following tool messages
            if removed.get("role") == "assistant" and removed.get("tool_calls"):
                while truncated and truncated[0].get("role") == "tool":
                    tool_msg = truncated.pop(0)
                    total_tokens -= len(self._encoding.encode(str(tool_msg.get("content", ""))))

        # Ensure we don't start with a tool message
        while truncated and truncated[0].get("role") == "tool":
            truncated.pop(0)

        return truncated

    async def _convert_response(self, content: str) -> str:
        """Convert YAML blocks in the response to HTML with resource links."""
        if not self._response_converter:
            return content

        try:
            return await self._response_converter.convert(content)
        except Exception:
            logger.exception("Error converting response")
            return content
