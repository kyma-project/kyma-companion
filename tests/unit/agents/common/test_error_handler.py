import pytest

from agents.common.error_handler import (
    summarization_execution_error_handler,
    token_counting_error_handler,
    tool_parsing_error_handler,
)


class TestErrorHandlerDecorators:
    """Test the new error handling decorators."""

    @pytest.mark.parametrize(
        "decorator,test_case,input_value,expected_result",
        [
            # tool_parsing_error_handler tests
            (
                tool_parsing_error_handler,
                "success",
                "test content",
                {"parsed": "test content"},
            ),
            (
                tool_parsing_error_handler,
                "failure",
                "test content",
                None,
            ),
            # token_counting_error_handler tests
            (
                token_counting_error_handler,
                "success",
                "hello world test",
                3,
            ),
            (
                token_counting_error_handler,
                "failure",
                "test content",
                0,
            ),
        ],
    )
    def test_sync_error_handlers(
        self, decorator, test_case, input_value, expected_result
    ):
        """Test synchronous error handler decorators with various scenarios."""

        if decorator == tool_parsing_error_handler:
            if test_case == "success":

                @decorator
                def test_function(content: str):
                    return {"parsed": content}

            else:  # failure case

                @decorator
                def test_function(content: str):
                    raise ValueError("Parsing failed")

        elif decorator == token_counting_error_handler:
            if test_case == "success":

                @decorator
                def test_function(content: str):
                    return len(content.split())

            else:  # failure case

                @decorator
                def test_function(content: str):
                    raise RuntimeError("Token counting failed")

        result = test_function(input_value)
        assert result == expected_result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case,input_value,expected_result,should_raise,exception_message",
        [
            # summarization_execution_error_handler success test
            (
                "success",
                "test content",
                "Summary of: test content",
                False,
                None,
            ),
            # summarization_execution_error_handler failure test
            (
                "failure",
                "test content",
                None,
                True,
                "Summarization failed",
            ),
        ],
    )
    async def test_summarization_execution_error_handler(
        self, test_case, input_value, expected_result, should_raise, exception_message
    ):
        """Test summarization_execution_error_handler with various scenarios."""

        if test_case == "success":

            @summarization_execution_error_handler
            async def test_function(content: str):
                return f"Summary of: {content}"

        else:  # failure case

            @summarization_execution_error_handler
            async def test_function(content: str):
                raise Exception("Summarization failed")

        if should_raise:
            with pytest.raises(Exception, match=exception_message):
                await test_function(input_value)
        else:
            result = await test_function(input_value)
            assert result == expected_result
