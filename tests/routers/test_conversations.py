import json
from collections.abc import AsyncGenerator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from agents.common.data import Message
from main import app
from routers.conversations import get_conversation_service
from services.conversation import Service


class MockService(Service):
    def __init__(self, expected_error=None):
        self.expected_error = expected_error

    def init_conversation(self) -> dict:
        return {"message": "Mock chat initialized!"}

    async def handle_request(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[bytes, None]:
        if self.expected_error:
            raise self.expected_error
        yield b"data: Test response\n\n"
        yield b"data: Another chunk\n\n"
        yield b"data: [DONE]\n\n"


@pytest.fixture(scope="function")
def client_factory():
    def _create_client(expected_error=None):
        mock_service = MockService(expected_error)

        def get_mock_service():
            return mock_service

        app.dependency_overrides[get_conversation_service] = get_mock_service

        test_client = TestClient(app)

        return test_client

    yield _create_client

    # Clear the override after all tests
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "conversation_id, input_message, expected_output, expected_error",
    [
        (
            1,
            {
                "query": "How to expose a Kyma application? What is the reason of getting crashloopbackoff in k8s pod?",
                "resource_kind": "",
                "resource_api_version": "",
                "resource_name": "",
                "namespace": "",
            },
            {"status_code": 200, "content-type": "text/event-stream; charset=utf-8"},
            None,
        ),
        (
            2,
            {
                "query": "How to expose a Kyma application? What is the reason of getting crashloopbackoff in k8s pod?",
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "my-pod",
                "namespace": "default",
            },
            {"status_code": 200, "content-type": "text/event-stream; charset=utf-8"},
            None,
        ),
        (
            3,
            {
                "query": "What is Kyma?",
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "my-pod",
                "namespace": "default",
            },
            {"status_code": 200, "content-type": "text/event-stream; charset=utf-8"},
            Exception("Test exception"),
        ),
    ],
)
def test_messages_endpoint(
    client_factory, conversation_id, input_message, expected_output, expected_error
):
    # Create a new client with the expected error
    test_client = client_factory(expected_error)

    response = test_client.post(
        f"/conversations/{conversation_id}/messages", json=input_message
    )

    assert response.status_code == expected_output["status_code"]
    assert response.headers["content-type"] == expected_output["content-type"]

    content = response.content

    if not expected_error:
        assert b"data: Test response" in content
        assert b"data: Another chunk" in content
        assert b"data: [DONE]" in content
    else:
        error_data = json.loads(content)
        assert error_data["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert "Error: Test exception" in error_data["message"]
