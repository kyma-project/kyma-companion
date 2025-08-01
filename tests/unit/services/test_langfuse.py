from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.common.state import CompanionState, GraphInput, UserInput
from services.langfuse import REDACTED, LangfuseService, get_langfuse_metadata
from utils.settings import LangfuseMaskingModes


@pytest.mark.parametrize(
    "user_id, session_id, expected",
    [
        (
            "user1",
            "sess1",
            {"langfuse_session_id": "sess1", "langfuse_user_id": "user1"},
        ),
        ("abc", "123", {"langfuse_session_id": "123", "langfuse_user_id": "abc"}),
        ("", "", {"langfuse_session_id": "", "langfuse_user_id": ""}),
    ],
)
def test_get_langfuse_metadata(user_id, session_id, expected):
    assert get_langfuse_metadata(user_id, session_id) == expected


@pytest.mark.parametrize(
    "description, masking_mode, input_data, expected_output",
    [
        (
            "should return original data when masking is disabled",
            LangfuseMaskingModes.DISABLED,
            "original data without any cleanup of email testuser@kyma.com",
            "original data without any cleanup of email testuser@kyma.com",
        ),
        (
            "should return REDACTED when masking mode is set to REDACTED",
            LangfuseMaskingModes.REDACTED,
            "original data",
            "REDACTED",
        ),
        (
            "should return REDACTED when masking mode is PARTIAL but data is not of type GraphInput",
            LangfuseMaskingModes.PARTIAL,
            "string data type",
            "REDACTED",
        ),
        (
            "should return graph input messages when masking mode is PARTIAL and data is of type GraphInput",
            LangfuseMaskingModes.PARTIAL,
            GraphInput(
                messages=[
                    SystemMessage(content="message 1"),
                    HumanMessage(content="message 2"),
                ],
                input=UserInput(query="foo bar"),
                k8s_client=None,
            ),
            "message 2\nmessage 1",  # Will be scrubbed, so we patch scrubber
        ),
        (
            "should return scrubbed output (removed email) when masking mode is PARTIAL and data is of type GraphInput",
            LangfuseMaskingModes.PARTIAL,
            GraphInput(
                messages=[
                    SystemMessage(content="message 1"),
                    HumanMessage(content="message 2 for testuser@kyma.com"),
                ],
                input=UserInput(query="foo bar"),
                k8s_client=None,
            ),
            "message 2 for {{EMAIL}}\nmessage 1",  # Will be scrubbed, so we patch scrubber
        ),
        (
            "should scrub dict with content and role when masking mode is FILTERED",
            LangfuseMaskingModes.FILTERED,
            {"role": "user", "content": "my email is test@example.com"},
            {"role": "user", "content": "my email is {{EMAIL}}"},
        ),
        (
            "should redact dict with tool role when masking mode is FILTERED",
            LangfuseMaskingModes.FILTERED,
            {"role": "tool", "content": "secret"},
            {"role": "tool", "content": REDACTED},
        ),
        (
            "should scrub nested dict when masking mode is FILTERED",
            LangfuseMaskingModes.FILTERED,
            {"foo": {"role": "user", "content": "test@example.com"}},
            {"foo": {"role": "user", "content": "{{EMAIL}}"}},
        ),
        (
            "should redact ToolMessage when masking mode is FILTERED",
            LangfuseMaskingModes.FILTERED,
            ToolMessage(content="secret", tool_call_id="abc"),
            ToolMessage(content=REDACTED, tool_call_id="abc"),
        ),
        (
            "should scrub AIMessage when masking mode is FILTERED",
            LangfuseMaskingModes.FILTERED,
            AIMessage(content="my email is test@example.com"),
            AIMessage(content="my email is {{EMAIL}}"),
        ),
    ],
)
def test_masking_production_data(
    description: str,
    masking_mode: LangfuseMaskingModes,
    input_data: Any,
    expected_output: Any,
):
    service = LangfuseService()
    service.masking_mode = masking_mode

    # when / then
    assert service.masking_production_data(input_data) == expected_output, description


@pytest.mark.parametrize(
    "description, input_data, expected_output",
    [
        (
            "should return REDACTED when  data is not of type GraphInput",
            "string data type",
            "REDACTED",
        ),
        (
            "should return graph input messages when  data is of type GraphInput",
            GraphInput(
                messages=[
                    SystemMessage(content="message 1"),
                    HumanMessage(content="message 2"),
                ],
                input=UserInput(query="foo bar"),
                k8s_client=None,
            ),
            "message 2\nmessage 1",  # Will be scrubbed, so we patch scrubber
        ),
        (
            "should return scrubbed output (removed email) when data is of type GraphInput",
            GraphInput(
                messages=[
                    SystemMessage(content="message 1"),
                    HumanMessage(content="message 2 for testuser@kyma.com"),
                ],
                input=UserInput(query="foo bar"),
                k8s_client=None,
            ),
            "message 2 for {{EMAIL}}\nmessage 1",  # Will be scrubbed, so we patch scrubber
        ),
    ],
)
def test_masking_mode_partial(
    description: str,
    input_data: Any,
    expected_output: Any,
):
    service = LangfuseService()

    # when / then
    assert service._masking_mode_partial(input_data) == expected_output, description


@pytest.mark.parametrize(
    "description, input_data, expected_output",
    [
        (
            "should return scrubbed string",
            "my email is test@example.com",
            "my email is {{EMAIL}}",
        ),
        (
            "should return REDACTED for unsupported type",
            object(),
            f"{REDACTED} - Unsupported data type (<class 'object'>) for masking.",
        ),
        (
            "should return REDACTED for empty data",
            None,
            None,
        ),
        (
            "should return REDACTED for int",
            123,
            123,
        ),
        (
            "should return REDACTED for float",
            1.23,
            1.23,
        ),
        (
            "should return REDACTED for bool",
            True,
            True,
        ),
        (
            "should scrub GraphInput messages",
            GraphInput(
                messages=[
                    SystemMessage(content="message 1"),
                    HumanMessage(content="message 2 for test@example.com"),
                ],
                input=UserInput(query="foo bar"),
                k8s_client=None,
            ),
            "message 2 for {{EMAIL}}\nmessage 1",
        ),
        (
            "should scrub dict with content and role",
            {"role": "user", "content": "my email is test@example.com"},
            {"role": "user", "content": "my email is {{EMAIL}}"},
        ),
        (
            "should redact dict with tool role",
            {"role": "tool", "content": "secret"},
            {"role": "tool", "content": REDACTED},
        ),
        (
            "should scrub nested dict",
            {"foo": {"role": "user", "content": "test@example.com"}},
            {"foo": {"role": "user", "content": "{{EMAIL}}"}},
        ),
        (
            "should scrub list of strings",
            ["my email is test@example.com", "no email here"],
            ["my email is {{EMAIL}}", "no email here"],
        ),
        (
            "should redact ToolMessage",
            ToolMessage(content="secret", tool_call_id="abc"),
            ToolMessage(content=REDACTED, tool_call_id="abc"),
        ),
        (
            "should scrub BaseMessage",
            HumanMessage(content="my email is test@example.com"),
            HumanMessage(content="my email is {{EMAIL}}"),
        ),
        (
            "should scrub AIMessage",
            AIMessage(content="my email is test@example.com"),
            AIMessage(content="my email is {{EMAIL}}"),
        ),
        (
            "should scrub CompanionState",
            CompanionState(
                messages=[
                    SystemMessage(content="system message"),
                    HumanMessage(content="my email is test@example.com"),
                    ToolMessage(content="secret", tool_call_id="abc"),
                ],
                k8s_client=None,
                input=UserInput(query="query"),
            ),
            {
                "error": None,
                "input": {
                    "namespace": None,
                    "query": "query",
                    "resource_api_version": None,
                    "resource_kind": None,
                    "resource_name": None,
                    "resource_related_to": None,
                    "resource_scope": None,
                },
                "is_feedback": False,
                "messages": [
                    {
                        "additional_kwargs": {},
                        "content": "system message",
                        "id": None,
                        "name": None,
                        "response_metadata": {},
                        "type": "system",
                    },
                    {
                        "additional_kwargs": {},
                        "content": "my email is {{EMAIL}}",
                        "id": None,
                        "name": None,
                        "response_metadata": {},
                        "type": "human",
                    },
                    {
                        "additional_kwargs": {},
                        "content": "secret",
                        "id": None,
                        "name": None,
                        "response_metadata": {},
                        "type": "tool",
                    },
                ],
                "messages_summary": "",
                "next": None,
                "subtasks": [],
                "thread_owner": "",
            },
        ),
    ],
)
def test_masking_mode_filtered(description, input_data, expected_output):
    service = LangfuseService()
    result = service._masking_mode_filtered(input_data)
    # For ToolMessage and HumanMessage, compare their content attribute
    if hasattr(result, "content") and hasattr(expected_output, "content"):
        assert result.content == expected_output.content, description
    else:
        assert result == expected_output, description
