import json
from collections.abc import AsyncGenerator
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from agents.common.constants import ERROR_RATE_LIMIT_CODE
from agents.common.data import Message
from main import app
from routers.conversations import authorize_user, init_conversation_service
from services.conversation import IService
from services.k8s import IK8sClient

SAMPLE_JWT_TOKEN = jwt.encode({"sub": "user123"}, "secret", algorithm="HS256")


#
class MockService(IService):
    def __init__(self, expected_error=None):
        self.expected_error = expected_error

    def new_conversation(self, k8s_client: IK8sClient, message: Message) -> list[str]:
        if self.expected_error:
            raise self.expected_error
        return ["Test question 1", "Test question 2", "Test question 3"]

    async def handle_followup_questions(self, conversation_id: str) -> list[str]:
        if self.expected_error:
            raise self.expected_error
        return [
            "Test follow-up question 1",
            "Test follow-up question 2",
            "Test follow-up question 3",
        ]

    async def authorize_user(self, conversation_id: str, user_identifier: str) -> bool:
        if user_identifier == "UNAUTHORIZED":
            return False
        return True

    async def is_usage_limit_exceeded(self, cluster_id: str) -> bool:
        """Check if the token usage limit is exceeded for the given cluster_id."""
        if cluster_id == "EXCEEDED":
            return True
        return False

    async def handle_request(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
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


@pytest.fixture(scope="function")
def client_factory():
    def _create_client(expected_error=None):
        mock_service = MockService(expected_error)

        def get_mock_service():
            return mock_service

        app.dependency_overrides[init_conversation_service] = get_mock_service
        test_client = TestClient(app)

        return test_client

    yield _create_client

    # Clear the override after all tests
    app.dependency_overrides.clear()


@patch("services.k8s.K8sClient.__init__", return_value=None)
@pytest.mark.parametrize(
    "request_headers, conversation_id, input_message, expected_output",
    [
        (
            {
                "x-k8s-authorization": SAMPLE_JWT_TOKEN,
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
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
            {
                "x-k8s-authorization": SAMPLE_JWT_TOKEN,
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
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
        (
            {},
            3,
            {
                "query": "should return error when k8s headers are missing",
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "my-pod",
                "namespace": "default",
            },
            {"status_code": 422, "content-type": "application/json"},
        ),
        (
            {
                "x-k8s-authorization": "invalid-token",
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            4,
            {
                "query": "How to expose a Kyma application? What is the reason of getting crashloopbackoff in k8s pod?",
                "resource_kind": "",
                "resource_api_version": "",
                "resource_name": "",
                "namespace": "",
            },
            {"status_code": 401, "content-type": "application/json"},
        ),
        (
            {
                "x-k8s-authorization": jwt.encode(
                    {"sub": "UNAUTHORIZED"}, "secret", algorithm="HS256"
                ),
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            5,
            {
                "query": "How to expose a Kyma application? What is the reason of getting crashloopbackoff in k8s pod?",
                "resource_kind": "",
                "resource_api_version": "",
                "resource_name": "",
                "namespace": "",
            },
            {"status_code": 403, "content-type": "application/json"},
        ),
        (
            {
                "x-k8s-authorization": SAMPLE_JWT_TOKEN,
                "x-cluster-url": "https://api.EXCEEDED.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            6,
            {
                "query": "Test query",
                "resource_kind": "",
                "resource_api_version": "",
                "resource_name": "",
                "namespace": "",
            },
            {
                "status_code": ERROR_RATE_LIMIT_CODE,
                "content-type": "application/json",
                "body": {
                    "detail": {
                        "error": "Rate limit exceeded",
                        "limit": 5000000,
                        "message": "Daily token limit exceeded for this cluster",
                        "time_remaining_seconds": 86400,
                    },
                },
            },
        ),
    ],
)
def test_messages_endpoint(
    mock_init,
    client_factory,
    request_headers,
    conversation_id,
    input_message,
    expected_output,
):
    # Create a new client with the expected error
    test_client = client_factory()

    response = test_client.post(
        f"/api/conversations/{conversation_id}/messages",
        json=input_message,
        headers=request_headers,
    )

    assert response.status_code == expected_output["status_code"]
    assert response.headers["content-type"] == expected_output["content-type"]

    if expected_output["status_code"] == HTTPStatus.UNPROCESSABLE_ENTITY:
        # return if test case is to check for missing headers.
        return
    if (
        expected_output["status_code"] == HTTPStatus.UNAUTHORIZED
        or expected_output["status_code"] == HTTPStatus.FORBIDDEN
        or expected_output["status_code"] == ERROR_RATE_LIMIT_CODE
    ):
        # return if test case is to check for invalid token.
        return

    content = response.content

    assert (
        b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"content": '
        b'"To create an API Rule in Kyma to expose a service externally", "tasks": []}}}\n'
        in content
    )
    assert (
        b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"content": '
        b'"To create a kubernetes deployment", "tasks": []}}}\n' in content
    )
    assert (
        b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"content'
        b'": "To create an API Rule in Kyma to expose a service externally", "tasks": '
        b'[]}}}\n{"event": "agent_action", "data": {"agent": "KubernetesAgent", "an'
        b'swer": {"content": "To create a kubernetes deployment", "tasks": []}}}\n'
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


@pytest.mark.parametrize(
    "request_headers, conversation_id, given_error, expected_output",
    [
        (
            # should successfully return follow-up questions.
            {
                "x-k8s-authorization": SAMPLE_JWT_TOKEN,
                "x-cluster-url": "https://api.k8s.example.com",
            },
            "a8172829-7f6c-4c76-aa16-e91edc7a14c9",
            None,
            {
                "status_code": 200,
                "content-type": "application/json",
                "body": {
                    "questions": [
                        "Test follow-up question 1",
                        "Test follow-up question 2",
                        "Test follow-up question 3",
                    ],
                },
            },
        ),
        (
            # should return error when conversation service fails.
            {
                "x-k8s-authorization": SAMPLE_JWT_TOKEN,
                "x-cluster-url": "https://api.k8s.example.com",
            },
            "d8725492-deb2-4d81-8ee1-ac74d61e84c5",
            ValueError("service failed"),
            {
                "status_code": 500,
                "content-type": "application/json",
                "body": {"detail": "service failed"},
            },
        ),
        (
            # should return error when user is not authorized.
            {
                "x-k8s-authorization": jwt.encode(
                    {"sub": "UNAUTHORIZED"}, "secret", algorithm="HS256"
                ),
                "x-cluster-url": "https://api.k8s.example.com",
            },
            "a8172829-7f6c-4c76-aa16-e91edc7a14c8",
            None,
            {
                "status_code": 403,
                "content-type": "application/json",
                "body": {"detail": "User not authorized to access the conversation"},
            },
        ),
        (
            # should return token usage exceeded error.
            {
                "x-k8s-authorization": SAMPLE_JWT_TOKEN,
                "x-cluster-url": "https://api.EXCEEDED.example.com",
            },
            "a8172829-7f6c-4c76-aa16-e91edc7a14c8",
            None,
            {
                "status_code": ERROR_RATE_LIMIT_CODE,
                "content-type": "application/json",
                "body": {
                    "detail": {
                        "error": "Rate limit exceeded",
                        "limit": 5000000,
                        "message": "Daily token limit exceeded for this cluster",
                        "time_remaining_seconds": 86400,
                    },
                },
            },
        ),
    ],
)
def test_followup_questions(
    client_factory,
    request_headers,
    conversation_id,
    given_error,
    expected_output,
):
    # given
    # Create a new client with the expected error
    test_client = client_factory(given_error)

    # when
    response = test_client.get(
        f"/api/conversations/{conversation_id}/questions",
        headers=request_headers,
    )

    # then
    assert response.status_code == expected_output["status_code"]
    assert response.headers["content-type"] == expected_output["content-type"]

    response_body = json.loads(response.content)
    if expected_output["status_code"] == HTTPStatus.OK:
        assert response_body["questions"] == expected_output["body"]["questions"]
    else:
        assert response_body == expected_output["body"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_description, conversation_id, token, user_identifier, is_authorized, expected_exception",
    [
        (
            "valid token, user authorized",
            "conversation1",
            jwt.encode({"sub": "user1"}, "secret", algorithm="HS256"),
            "user1",
            True,
            None,
        ),
        (
            "valid token, user not authorized",
            "conversation2",
            jwt.encode({"sub": "user2"}, "secret", algorithm="HS256"),
            "user2",
            False,
            HTTPException,
        ),
        (
            "invalid token",
            "conversation3",
            "invalid_token",
            None,
            None,
            HTTPException,
        ),
    ],
)
async def test_authorize_user(
    test_description,
    conversation_id,
    token,
    user_identifier,
    is_authorized,
    expected_exception,
):
    # Mock the conversation_service
    mock_conversation_service = Mock()
    mock_conversation_service.authorize_user = AsyncMock(return_value=is_authorized)

    if expected_exception or not is_authorized:
        with pytest.raises(expected_exception):
            await authorize_user(conversation_id, token, mock_conversation_service)
    else:
        await authorize_user(conversation_id, token, mock_conversation_service)
        mock_conversation_service.authorize_user.assert_called_once_with(
            conversation_id, user_identifier
        )
