import json
from collections.abc import AsyncGenerator
from http import HTTPStatus
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agents.common.data import Message
from main import app
from routers.conversations import get_conversation_service
from services.conversation import IService
from services.k8s import IK8sClient


class MockService(IService):
    def __init__(self, expected_error=None):
        self.expected_error = expected_error

    async def new_conversation(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> list[str]:
        if self.expected_error:
            raise self.expected_error
        return ["Test question 1", "Test question 2", "Test question 3"]

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
        f"/api/conversations/{conversation_id}/messages", json=input_message
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


@pytest.mark.parametrize(
    "test_description, request_headers, request_body, given_error, expected_output",
    [
        (
            "should successfully initialize a conversation",
            {
                "x-k8s-authorization": "non-empty-auth",
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            {
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "nginx-123",
                "namespace": "default",
            },
            None,
            {
                "status_code": 200,
                "content-type": "application/json",
                "body": {
                    "initial_questions": [
                        "Test question 1",
                        "Test question 2",
                        "Test question 3",
                    ],
                },
            },
        ),
        (
            "should return error when k8s headers are missing",
            {},
            {
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "nginx-123",
                "namespace": "default",
            },
            None,
            {
                "status_code": 422,
                "content-type": "application/json",
                "body": {
                    "detail": [
                        {
                            "type": "missing",
                            "loc": ["header", "x-cluster-url"],
                            "msg": "Field required",
                            "input": None,
                        },
                        {
                            "type": "missing",
                            "loc": ["header", "x-k8s-authorization"],
                            "msg": "Field required",
                            "input": None,
                        },
                        {
                            "type": "missing",
                            "loc": ["header", "x-cluster-certificate-authority-data"],
                            "msg": "Field required",
                            "input": None,
                        },
                    ]
                },
            },
        ),
        (
            "should return error when copnversation service fails",
            {
                "x-k8s-authorization": "non-empty-auth",
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            {
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "nginx-123",
                "namespace": "default",
            },
            ValueError("service failed"),
            {
                "status_code": 500,
                "content-type": "application/json",
                "body": {"detail": "service failed"},
            },
        ),
    ],
)
@patch("services.k8s.K8sClient.__init__", return_value=None)
def test_init_conversation(
    mock_init,
    client_factory,
    test_description,
    request_headers,
    request_body,
    given_error,
    expected_output,
):
    # Create a new client with the expected error
    test_client = client_factory(given_error)

    response = test_client.post(
        "/api/conversations",
        json=request_body,
        headers=request_headers,
    )

    assert response.status_code == expected_output["status_code"]
    assert response.headers["content-type"] == expected_output["content-type"]

    response_body = json.loads(response.content)

    if expected_output["status_code"] == HTTPStatus.OK:
        assert (
            response_body["initial_questions"]
            == expected_output["body"]["initial_questions"]
        )
        assert response_body["conversation_id"] != ""
        assert response.headers["session-id"] != ""
    else:
        assert response_body == expected_output["body"]
