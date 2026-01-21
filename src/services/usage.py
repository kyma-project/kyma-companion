import time
from typing import Any, Protocol
from uuid import UUID

import pydantic
from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema import LLMResult
from pydantic import BaseModel

from agents.memory.async_redis_checkpointer import IUsageMemory
from routers.probes import IUsageTrackerProbe
from services.metrics import CustomMetrics, LangGraphErrorType
from services.probes import get_usage_tracker_probe
from utils.settings import TOKEN_USAGE_RESET_INTERVAL


class UsageModel(BaseModel):
    """Usage model for the token usage."""

    input: int
    output: int
    total: int
    epoch: float = time.time()


class UsageExceedReport(BaseModel):
    """Usage exceed report model."""

    cluster_id: str
    token_limit: int
    total_tokens_used: int
    reset_seconds_left: int


class UsageTrackerCallback(AsyncCallbackHandler):
    """langChain callback handler to track the token usage.
    Reference: https://python.langchain.com/docs/concepts/callbacks/
    """

    def __init__(
        self,
        cluster_id: str,
        memory: IUsageMemory,
        probe: IUsageTrackerProbe | None = None,
    ):
        self.cluster_id = cluster_id
        self.memory = memory
        self.ttl = TOKEN_USAGE_RESET_INTERVAL
        self.llm_start_times: dict = {}
        self._probe = probe or get_usage_tracker_probe()

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Overridden callback method to record the LLM start time."""
        self.llm_start_times[run_id] = time.perf_counter()

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Overridden callback method to track the token usage."""
        try:
            # first save llm response time.
            # note that the start time would be zero if the start time was not recorded.
            await CustomMetrics().record_llm_latency(time.perf_counter() - self.llm_start_times.pop(run_id, 0.0))

            # publish token usage info to the memory.
            usage = _parse_usage(response)
            if usage is None:
                raise ValueError("Usage information not found in the LLM response.")
            # parse the usage as Pydantic model to verify the structure.
            usage_model = UsageModel(**usage)
            await self.memory.awrite_llm_usage(self.cluster_id, usage_model.__dict__, self.ttl)

            # reset the failure count we track in the probe.
            self._probe.reset_failure_count()
        except Exception as e:
            # track the failure in the probe.
            self._probe.increase_failure_count()
            await CustomMetrics().record_token_usage_tracker_publish_failure()
            raise e

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Overridden callback method to record the LLM error."""
        await CustomMetrics().record_langgraph_error(LangGraphErrorType.LLM_ERROR)

    async def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Overridden callback method to record the retriever error."""
        await CustomMetrics().record_langgraph_error(LangGraphErrorType.RETRIEVER_ERROR)

    async def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Overridden callback method to record the chain error."""
        await CustomMetrics().record_langgraph_error(LangGraphErrorType.CHAIN_ERROR)

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Overridden callback method to record the tool error."""
        await CustomMetrics().record_langgraph_error(LangGraphErrorType.TOOL_ERROR)


class IUsageTracker(Protocol):
    """Interface for the UsageTracker."""

    async def adelete_expired_records(self, cluster_id: str) -> None:
        """Delete the expired records for the given cluster_id."""

    async def ais_usage_limit_exceeded(self, cluster_id: str) -> UsageExceedReport | None:
        """Check if the token limit is exceeded for the given cluster_id."""


class UsageTracker(IUsageTracker):
    """Usage tracker to check the token usage."""

    def __init__(self, memory: IUsageMemory, token_limit: int, reset_interval_sec: int):
        self.memory = memory
        self.reset_interval_sec: int = reset_interval_sec
        self.token_limit: int = token_limit

    async def adelete_expired_records(self, cluster_id: str) -> None:
        """Delete the expired records for the given cluster_id."""
        await self.memory.adelete_expired_llm_usage_records(cluster_id, self.reset_interval_sec)

    async def ais_usage_limit_exceeded(self, cluster_id: str) -> UsageExceedReport | None:
        """Check if the token limit is exceeded for the given cluster_id."""
        if self.token_limit == -1:
            return None
        records = await self.memory.alist_llm_usage_records(cluster_id, self.reset_interval_sec)
        # parse the records as Pydantic model to verify the structure.
        records = [UsageModel(**record) for record in records]
        total_usage = sum(record.total for record in records)

        # return if token usage limit is not exceeded.
        if total_usage < self.token_limit:
            return None

        # find the latest record to calculate the reset_seconds_left
        latest_record = max(records, key=lambda record: record.epoch)
        reset_seconds_left = int(float(self.reset_interval_sec) - (time.time() - latest_record.epoch))

        return UsageExceedReport(
            cluster_id=cluster_id,
            token_limit=self.token_limit,
            total_tokens_used=total_usage,
            reset_seconds_left=reset_seconds_left,
        )


# Helper methods


def _parse_usage(response: LLMResult) -> dict[str, Any] | None:
    """Parse the token usage information from the LLM response.
    This method is inspired by LangFuse's usage parsing logic.
    https://github.com/langfuse/langfuse-python/blob/07a1993ff428d67c3b9fdd12585e6de6e128d20b/langfuse/callback/langchain.py#L1116
    """
    # langchain-anthropic uses the usage field
    llm_usage_keys = ["token_usage", "usage"]
    llm_usage = None
    if response.llm_output is not None:
        for key in llm_usage_keys:
            if key in response.llm_output and response.llm_output[key]:
                llm_usage = _parse_usage_model(response.llm_output[key])
                break

    if hasattr(response, "generations"):
        for generation in response.generations:
            for generation_chunk in generation:
                if generation_chunk.generation_info and ("usage_metadata" in generation_chunk.generation_info):
                    llm_usage = _parse_usage_model(generation_chunk.generation_info["usage_metadata"])
                    break

                message_chunk = getattr(generation_chunk, "message", {})
                response_metadata = getattr(message_chunk, "response_metadata", {})

                chunk_usage = (
                    (
                        response_metadata.get("usage", None)  # for Bedrock-Anthropic
                        if isinstance(response_metadata, dict)
                        else None
                    )
                    or (
                        response_metadata.get("amazon-bedrock-invocationMetrics", None)  # for Bedrock-Titan
                        if isinstance(response_metadata, dict)
                        else None
                    )
                    or getattr(message_chunk, "usage_metadata", None)  # for Ollama
                )

                if chunk_usage:
                    llm_usage = _parse_usage_model(chunk_usage)
                    break

    return llm_usage


def _parse_usage_model(usage: pydantic.BaseModel | dict) -> dict[str, Any] | None:
    """Parse the token usage model from the LLM response.
    This method is inspired by LangFuse's usage parsing logic.
    https://github.com/langfuse/langfuse-python/blob/07a1993ff428d67c3b9fdd12585e6de6e128d20b/langfuse/callback/langchain.py#L1116
    """
    # maintains a list of key translations. For each key, the usage model is checked
    # and a new object will be created with the new key if the key exists in the usage model
    # All non-matched keys will remain on the object.

    if hasattr(usage, "__dict__"):
        usage = usage.__dict__

    conversion_list = [
        # https://pypi.org/project/langchain-anthropic/ (works also for Bedrock-Anthropic)
        ("input_tokens", "input"),
        ("output_tokens", "output"),
        ("total_tokens", "total"),
        # https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/get-token-count
        ("prompt_token_count", "input"),
        ("candidates_token_count", "output"),
        # Bedrock: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-cw.html#runtime-cloudwatch-metrics
        ("inputTokenCount", "input"),
        ("outputTokenCount", "output"),
        ("totalTokenCount", "total"),
        # langchain-ibm https://pypi.org/project/langchain-ibm/
        ("input_token_count", "input"),
        ("generated_token_count", "output"),
        # OpenAI
        ("prompt_tokens", "input"),
        ("completion_tokens", "output"),
        ("total_tokens", "total"),
    ]

    usage_model = usage.copy()  # Copy all existing key-value pairs

    for model_key, langfuse_key in conversion_list:
        if model_key in usage_model:
            captured_count = usage_model.pop(model_key)
            final_count = (
                sum(captured_count) if isinstance(captured_count, list) else captured_count
            )  # For Bedrock, the token count is a list when streamed

            usage_model[langfuse_key] = final_count  # type: ignore

    if isinstance(usage_model, pydantic.BaseModel):
        return dict(usage_model)

    return usage_model if usage_model else None
