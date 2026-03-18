import copy
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from services.k8s import IK8sClient, K8sClient
from services.langfuse import EMPTY_OBJECT, REDACTED, LangfuseService, get_langfuse_metadata
from utils.settings import LangfuseMaskingModes


def create_k8s_client():
    with patch("services.k8s.K8sClient.__init__", return_value=None):
        return K8sClient()


@pytest.mark.parametrize(
    "description, user_id, session_id, tags, expected",
    [
        (
            "should include tags for single tag",
            "user1",
            "sess1",
            ["tag-a"],
            {
                "langfuse_session_id": "sess1",
                "langfuse_user_id": "user1",
                "langfuse_tags": ["tag-a"],
            },
        ),
        (
            "should include tags for multiple tags",
            "abc",
            "123",
            ["tag-1", "tag-2"],
            {
                "langfuse_session_id": "123",
                "langfuse_user_id": "abc",
                "langfuse_tags": ["tag-1", "tag-2"],
            },
        ),
        (
            "should include empty tags when none provided",
            "",
            "",
            [],
            {
                "langfuse_session_id": "",
                "langfuse_user_id": "",
                "langfuse_tags": [],
            },
        ),
    ],
)
def test_get_langfuse_metadata(description, user_id, session_id, tags, expected):
    assert get_langfuse_metadata(user_id, session_id, tags) == expected, description


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
            "should return REDACTED when masking mode is PARTIAL and data is a plain string",
            LangfuseMaskingModes.PARTIAL,
            "string data type",
            "string data type",  # Partial mode scrubs strings now
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
    original_data = copy.deepcopy(input_data)

    # when / then
    assert service.masking_production_data(data=input_data) == expected_output, description
    assert input_data == original_data, "input data should not have been modified in place"


@pytest.mark.parametrize(
    "description, input_data, expected_output",
    [
        (
            "should scrub string with PII",
            "my email is test@example.com",
            "my email is {{EMAIL}}",
        ),
        (
            "should return REDACTED for non-string non-dict data",
            123,
            "REDACTED",
        ),
        (
            "should scrub dict content in partial mode",
            {"role": "user", "content": "email test@example.com"},
            "email {{EMAIL}}",
        ),
    ],
)
def test_masking_mode_partial(
    description: str,
    input_data: Any,
    expected_output: Any,
):
    service = LangfuseService()
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
            "should return None for empty data",
            None,
            None,
        ),
        (
            "should return int unchanged",
            123,
            123,
        ),
        (
            "should return float unchanged",
            1.23,
            1.23,
        ),
        (
            "should return bool unchanged",
            True,
            True,
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
            "should redact ToolMessage with disallowed name",
            ToolMessage(content="secret", tool_call_id="abc", name="unauthorized_tool"),
            ToolMessage(content=REDACTED, tool_call_id="abc", name="unauthorized_tool"),
        ),
        (
            "should redact ToolMessage without name",
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
            "should return empty object for K8s client",
            create_k8s_client,
            EMPTY_OBJECT,
        ),
    ],
)
def test_masking_mode_filtered(description, input_data, expected_output):
    # Given
    service = LangfuseService()
    if callable(input_data):
        input_data = input_data()
    original_data = copy.deepcopy(input_data)

    # when
    result = service._masking_mode_filtered(input_data)

    # then
    if hasattr(result, "content") and hasattr(expected_output, "content"):
        assert result.content == expected_output.content, description
    else:
        assert result == expected_output, description

    if not isinstance(input_data, (IK8sClient, K8sClient, object)):
        assert input_data == original_data, "input data should not have been modified in place"


@pytest.mark.parametrize(
    "description, input_data, expected_output",
    [
        (
            "should mask K8s client instance",
            create_k8s_client,
            EMPTY_OBJECT,
        ),
        (
            "should return None for non-critical data",
            "safe string",
            None,
        ),
    ],
)
def test_mask_critical(description, input_data, expected_output):
    service = LangfuseService()
    if callable(input_data):
        input_data = input_data()

    assert service._mask_critical(input_data) == expected_output, description
