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


#
class MockService(IService):
    def __init__(self, expected_error=None):
        self.expected_error = expected_error

    def new_conversation(
        self, session_id: str, k8s_client: IK8sClient, message: Message
    ) -> list[str]:
        if self.expected_error:
            raise self.expected_error
        return ["Test question 1", "Test question 2", "Test question 3"]

    async def handle_request(
        self, conversation_id: str, message: Message
    ) -> AsyncGenerator[bytes, None]:
        if self.expected_error:
            raise self.expected_error
        yield (
            b'{"KymaAgent": {"messages": [{"content": '
            b'"To create an API Rule in Kyma to expose a service externally", "additional_kwargs": {}, '
            b'"response_metadata": {}, "type": "ai", "name": "Supervisor", "id": null, '
            b'"example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}]}}'
        )
        yield (
            b'{"KubernetesAgent": {"messages": [{"content": "To create a kubernetes deployment", '
            b'"additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Supervisor", '
            b'"id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], '
            b'"usage_metadata": null}]}}'
        )
        yield (
            b'{"Exit": {"next": "__end__", "final_response": "To create a Kubernetes application '
            b'and expose it when deployed in the Kyma runtime"}}'
        )


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
    "conversation_id, input_message, expected_output",
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
        ),
    ],
)
def test_messages_endpoint(
    client_factory, conversation_id, input_message, expected_output
):
    # Create a new client with the expected error
    test_client = client_factory()

    response = test_client.post(
        f"/api/conversations/{conversation_id}/messages", json=input_message
    )

    assert response.status_code == expected_output["status_code"]
    assert response.headers["content-type"] == expected_output["content-type"]

    content = response.content

    assert (
        b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"messages": [{"content": '
        b'"To create an API Rule in Kyma to expose a service externally"}]}}}'
        in content
    )
    assert (
        b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"messages": [{"content": '
        b'"To create a kubernetes deployment"}]}}}' in content
    )
    assert (
        b'{"event": "final_response", "data": {"answer": '
        b'"To create a Kubernetes application and expose it when deployed in the Kyma runtime"}}'
        in content
    )


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
            "should return error when conversation service fails",
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
