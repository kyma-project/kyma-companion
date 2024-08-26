import os
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from agents.common.data import Message

if not os.getenv("MODELS_CONFIG_FILE_PATH"):
    os.environ["MODELS_CONFIG_FILE_PATH"] = "../config/config.yml"

mock_proxy_client = MagicMock()


@pytest.mark.parametrize(
    "conversation_id, input_message, expected_output, expected_error",
    [
        (
            1,
            {
                "query": "How to expose a Kyma application? What is the reason of getting crashloopbackoff in k8s pod?",
                "resource_type": "",
                "resource_name": "",
                "namespace": "",
            },
            {"status_code": 200, "content-type": "text/event-stream"},
            None,
        ),
        (
            2,
            {
                "query": "How to expose a Kyma application? What is the reason of getting crashloopbackoff in k8s pod?",
                "resource_type": "Pod",
                "resource_name": "my-pod",
                "namespace": "default",
            },
            {"status_code": 200, "content-type": "text/event-stream"},
            None,
        ),
        (
            3,
            {
                "query": "How to expose a Kyma application? What is the reason of getting crashloopbackoff in k8s pod?",
                "resource_type": "Pod",
                "resource_name": "my-pod",
                "namespace": "default",
            },
            {"status_code": 500, "content-type": "application/json"},
            Exception("Test exception"),
        ),
    ],
)
@pytest.mark.asyncio
@patch("utils.models.get_proxy_client", mock_proxy_client)
async def test_messages_endpoint(
    mocker, conversation_id, input_message, expected_output, expected_error
):
    mocker.patch("services.messages.MessagesService.__init__", return_value=None)

    # Mock the handle_request method to return an AsyncIterator[bytes]
    async def mock_handle_request(
        conv_id: int, message: Message
    ) -> AsyncGenerator[bytes, None]:
        if expected_error:
            raise Exception("fake error")
        yield b"data: Test response\n\n"
        yield b"data: Another chunk\n\n"
        yield b"data: [DONE]\n\n"

    mocker.patch(
        "routers.conversations.messages_service.handle_request",
        side_effect=mock_handle_request,
    )

    from main import app

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            f"/conversations/{conversation_id}/messages", json=input_message
        )
    content = b""
    async for chunk in response.aiter_bytes():
        content += chunk

    if not expected_error:
        assert b"data: Test response\\n\\n" in content
        assert b"data: Another chunk\\n\\n" in content
        assert b"data: [DONE]\\n\\n" in content
    else:
        assert b"Error: fake error" in content
