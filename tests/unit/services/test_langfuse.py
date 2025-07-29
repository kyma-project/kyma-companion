from typing import Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common.state import GraphInput, UserInput
from services.langfuse import LangfuseService
from utils.settings import LangfuseMaskingModes


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
