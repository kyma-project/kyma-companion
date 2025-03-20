import time
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langchain_core.outputs import ChatGeneration, LLMResult

from services.metrics import (
    LANGGRAPH_ERROR_METRIC_KEY,
    USAGE_TRACKER_PUBLISH_FAILURE_METRIC_KEY,
    CustomMetrics,
    LangGraphErrorType,
)
from services.usage import (
    UsageExceedReport,
    UsageTracker,
    UsageTrackerCallback,
    _parse_usage,
    _parse_usage_model,
)


class TestUsageTrackerCallback:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_description, llm_output, expected_exception, expected_call_args",
        [
            (
                "should write usage when usage information is present",
                {
                    "token_usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                    },
                },
                None,
                {
                    "input": 100,
                    "output": 50,
                    "total": 150,
                    "epoch": None,
                },
            ),
            (
                "should raise ValueError when usage information is not present",
                None,
                ValueError,
                None,
            ),
        ],
    )
    async def test_on_llm_end(
        self, test_description, llm_output, expected_exception, expected_call_args
    ):
        # Given
        mock_memory = Mock()
        mock_memory.awrite_llm_usage = AsyncMock()
        usage_tracker_callback = UsageTrackerCallback(
            cluster_id="test_cluster", memory=mock_memory
        )
        response = Mock()
        response.llm_output = llm_output
        response.generations = []
        metric_name = f"{USAGE_TRACKER_PUBLISH_FAILURE_METRIC_KEY}_total"
        before_metric_value = CustomMetrics().registry.get_sample_value(metric_name)

        # When / Then
        if expected_exception:
            with pytest.raises(
                expected_exception,
                match="Usage information not found in the LLM response.",
            ):
                await usage_tracker_callback.on_llm_end(response, run_id=uuid4())

            # the metric should be increased.
            after_metric_value = CustomMetrics().registry.get_sample_value(metric_name)
            assert after_metric_value > before_metric_value
        else:
            await usage_tracker_callback.on_llm_end(response, run_id=uuid4())
            call_args = mock_memory.awrite_llm_usage.call_args[0][1]
            call_args["epoch"] = None  # Ignore epoch for comparison
            assert call_args == expected_call_args
            mock_memory.awrite_llm_usage.assert_called_once_with(
                "test_cluster", expected_call_args, usage_tracker_callback.ttl
            )
            # the metric should not be increased.
            after_metric_value = CustomMetrics().registry.get_sample_value(metric_name)
            assert after_metric_value == before_metric_value

    @pytest.mark.asyncio
    async def test_on_llm_error(
        self,
    ):
        # given
        usage_tracker_callback = UsageTrackerCallback(
            cluster_id="test_cluster", memory=Mock()
        )
        metric_name = f"{LANGGRAPH_ERROR_METRIC_KEY}_total"
        labels = {"error_type": LangGraphErrorType.LLM_ERROR.value}
        before_metric_value = CustomMetrics().registry.get_sample_value(
            metric_name, labels
        )
        if before_metric_value is None:
            before_metric_value = 0

        # when
        await usage_tracker_callback.on_llm_error(None, run_id=uuid4())

        # then
        # the metric should be increased.
        after_metric_value = CustomMetrics().registry.get_sample_value(
            metric_name, labels
        )
        assert after_metric_value > before_metric_value

    @pytest.mark.asyncio
    async def test_on_retriever_error(
        self,
    ):
        # given
        usage_tracker_callback = UsageTrackerCallback(
            cluster_id="test_cluster", memory=Mock()
        )
        metric_name = f"{LANGGRAPH_ERROR_METRIC_KEY}_total"
        labels = {"error_type": LangGraphErrorType.RETRIEVER_ERROR.value}
        before_metric_value = CustomMetrics().registry.get_sample_value(
            metric_name, labels
        )
        if before_metric_value is None:
            before_metric_value = 0

        # when
        await usage_tracker_callback.on_retriever_error(None, run_id=uuid4())

        # then
        # the metric should be increased.
        after_metric_value = CustomMetrics().registry.get_sample_value(
            metric_name, labels
        )
        assert after_metric_value > before_metric_value

    @pytest.mark.asyncio
    async def test_on_chain_error(
        self,
    ):
        # given
        usage_tracker_callback = UsageTrackerCallback(
            cluster_id="test_cluster", memory=Mock()
        )
        metric_name = f"{LANGGRAPH_ERROR_METRIC_KEY}_total"
        labels = {"error_type": LangGraphErrorType.CHAIN_ERROR.value}
        before_metric_value = CustomMetrics().registry.get_sample_value(
            metric_name, labels
        )
        if before_metric_value is None:
            before_metric_value = 0

        # when
        await usage_tracker_callback.on_chain_error(None, run_id=uuid4())

        # then
        # the metric should be increased.
        after_metric_value = CustomMetrics().registry.get_sample_value(
            metric_name, labels
        )
        assert after_metric_value > before_metric_value

    @pytest.mark.asyncio
    async def test_on_tool_error(
        self,
    ):
        # given
        usage_tracker_callback = UsageTrackerCallback(
            cluster_id="test_cluster", memory=Mock()
        )
        metric_name = f"{LANGGRAPH_ERROR_METRIC_KEY}_total"
        labels = {"error_type": LangGraphErrorType.TOOL_ERROR.value}
        before_metric_value = CustomMetrics().registry.get_sample_value(
            metric_name, labels
        )
        if before_metric_value is None:
            before_metric_value = 0

        # when
        await usage_tracker_callback.on_tool_error(None, run_id=uuid4())

        # then
        # the metric should be increased.
        after_metric_value = CustomMetrics().registry.get_sample_value(
            metric_name, labels
        )
        assert after_metric_value > before_metric_value


class TestUsageTracker:
    @pytest.mark.asyncio
    async def test_adelete_expired_records(self):
        # Given
        mock_memory = Mock()
        mock_memory.adelete_expired_llm_usage_records = AsyncMock()
        usage_tracker = UsageTracker(
            memory=mock_memory, token_limit=1000, reset_interval_sec=3600
        )
        cluster_id = "test_cluster"

        # When
        await usage_tracker.adelete_expired_records(cluster_id)

        # Then
        mock_memory.adelete_expired_llm_usage_records.assert_called_once_with(
            cluster_id, 3600
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_description, token_limit, usage_records, expected_report",
        [
            (
                "should return None when token limit is -1",
                -1,
                [],
                None,
            ),
            (
                "should return None when token usage is below the limit",
                200,
                [
                    {
                        "input": 100,
                        "output": 50,
                        "total": 150,
                        "epoch": time.time(),
                    }
                ],
                None,
            ),
            (
                "should return report when token usage is above the limit",
                400,
                [
                    {
                        "input": 100,
                        "output": 150,
                        "total": 250,
                        "epoch": time.time() - 20,  # 20 seconds old record
                    },
                    {
                        "input": 100,
                        "output": 150,
                        "total": 250,
                        "epoch": time.time() - 10,  # 10 seconds old record
                    },
                ],
                UsageExceedReport(
                    cluster_id="test_cluster",
                    token_limit=400,
                    total_tokens_used=500,
                    reset_seconds_left=600,
                ),
            ),
        ],
    )
    async def test_is_usage_limit_exceeded(
        self, test_description, token_limit, usage_records, expected_report
    ):
        # Given
        reset_interval_sec = 600
        mock_memory = Mock()
        mock_memory.alist_llm_usage_records = AsyncMock()
        mock_memory.alist_llm_usage_records.return_value = usage_records
        usage_tracker = UsageTracker(
            memory=mock_memory,
            token_limit=token_limit,
            reset_interval_sec=reset_interval_sec,
        )

        # When
        report = await usage_tracker.ais_usage_limit_exceeded("test_cluster")

        # Then
        if token_limit == -1 or expected_report is None:
            assert report is None
            return

        # for comparison, set the reset_seconds_left to the actual report.
        # we will check the reset_seconds_left separately.
        expected_report.reset_seconds_left = report.reset_seconds_left
        assert report == expected_report
        mock_memory.alist_llm_usage_records.assert_called_once_with(
            "test_cluster", reset_interval_sec
        )

        # check the reset_seconds_left.
        latest_record = max(usage_records, key=lambda record: record["epoch"])
        expected_reset_seconds_left = int(
            float(reset_interval_sec) - (time.time() - latest_record["epoch"])
        )
        # reset_seconds_left can be off by 5 second due to dynamic time.time().
        accepted_offset = 5
        assert (
            abs(report.reset_seconds_left - expected_reset_seconds_left)
            <= accepted_offset
        )


@pytest.mark.parametrize(
    "test_description, input_data, expected_output",
    [
        (
            "should parse input and output tokens correctly from the input 1",
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
            {
                "input": 100,
                "output": 50,
                "total": 150,
            },
        ),
        (
            "should parse input and output tokens correctly from the input 2",
            {
                "prompt_token_count": 100,
                "candidates_token_count": 50,
                "total_tokens": 150,
            },
            {
                "input": 100,
                "output": 50,
                "total": 150,
            },
        ),
        (
            "should parse input and output tokens correctly from the input 3",
            {
                "inputTokenCount": 100,
                "outputTokenCount": 50,
                "totalTokenCount": 150,
            },
            {
                "input": 100,
                "output": 50,
                "total": 150,
            },
        ),
        (
            "should parse input and output tokens correctly from the input 4",
            {
                "input_token_count": 100,
                "generated_token_count": 50,
                "total_tokens": 150,
            },
            {
                "input": 100,
                "output": 50,
                "total": 150,
            },
        ),
        (
            "should parse input and output tokens correctly from the input 5",
            {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
            {
                "input": 100,
                "output": 50,
                "total": 150,
            },
        ),
        (
            "should handle empty input",
            {},
            None,
        ),
    ],
)
def test_parse_usage_model(test_description, input_data, expected_output):
    # When
    result = _parse_usage_model(input_data)

    # Then
    assert result == expected_output


@pytest.mark.parametrize(
    "test_description, llm_result, expected_output",
    [
        (
            "should parse usage from llm_output with key token_usage",
            LLMResult(
                llm_output={
                    "token_usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                    }
                },
                generations=[],
            ),
            {"input": 100, "output": 50, "total": 150},
        ),
        (
            "should parse usage from llm_output with key usage",
            LLMResult(
                llm_output={
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                    }
                },
                generations=[],
            ),
            {"input": 100, "output": 50, "total": 150},
        ),
        (
            "should parse usage from generations with usage_metadata",
            LLMResult(
                llm_output=None,
                generations=[
                    [
                        {
                            "text": "test",
                            "generation_info": {
                                "usage_metadata": {
                                    "input_tokens": 100,
                                    "output_tokens": 50,
                                    "total_tokens": 150,
                                }
                            },
                        }
                    ],
                ],
            ),
            {"input": 100, "output": 50, "total": 150},
        ),
        (
            "should parse usage from generations with usage in response_metadata",
            LLMResult(
                llm_output=None,
                generations=[
                    [
                        ChatGeneration(
                            text="test",
                            message={
                                "type": "system",
                                "content": "test",
                                "response_metadata": {
                                    "usage": {
                                        "input_tokens": 100,
                                        "output_tokens": 50,
                                        "total_tokens": 150,
                                    }
                                },
                            },
                        )
                    ],
                ],
            ),
            {"input": 100, "output": 50, "total": 150},
        ),
        (
            "should parse usage from generations with amazon-bedrock-invocationMetrics in response_metadata",
            LLMResult(
                llm_output=None,
                generations=[
                    [
                        ChatGeneration(
                            text="test",
                            message={
                                "type": "system",
                                "content": "test",
                                "response_metadata": {
                                    "amazon-bedrock-invocationMetrics": {
                                        "input_tokens": 100,
                                        "output_tokens": 50,
                                        "total_tokens": 150,
                                    }
                                },
                            },
                        )
                    ],
                ],
            ),
            {"input": 100, "output": 50, "total": 150},
        ),
        (
            "should parse usage from generations with usage_metadata in message",
            LLMResult(
                llm_output=None,
                generations=[
                    [
                        ChatGeneration(
                            text="test",
                            message={
                                "type": "system",
                                "content": "test",
                                "usage_metadata": {
                                    "input_tokens": 100,
                                    "output_tokens": 50,
                                    "total_tokens": 150,
                                },
                            },
                        )
                    ],
                ],
            ),
            {"input": 100, "output": 50, "total": 150},
        ),
    ],
)
def test_parse_usage(test_description, llm_result, expected_output):
    # When
    result = _parse_usage(llm_result)

    # Then
    assert result == expected_output
