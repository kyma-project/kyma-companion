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
from routers.conversations import (
    authorize_user,
    check_token_usage,
    init_conversation_service,
)
from services.conversation import IService
from services.k8s import IK8sClient, K8sAuthHeaders
from services.usage import UsageExceedReport

SAMPLE_JWT_TOKEN = jwt.encode({"sub": "user123"}, "secret", algorithm="HS256")
SAMPLE_CLIENT_CERTIFICATE_DATA = "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJrakNDQVRlZ0F3SUJBZ0lJTmpJSzErZmhrZUF3Q2dZSUtvWkl6ajBFQXdJd0l6RWhNQjhHQTFVRUF3d1kKYXpOekxXTnNhV1Z1ZEMxallVQXhOelF4TXpReE1qRXlNQjRYRFRJMU1ETXdOekE1TlRNek1sb1hEVEkyTURNdwpOekE1TlRNek1sb3dNREVYTUJVR0ExVUVDaE1PYzNsemRHVnRPbTFoYzNSbGNuTXhGVEFUQmdOVkJBTVRESE41CmMzUmxiVHBoWkcxcGJqQlpNQk1HQnlxR1NNNDlBZ0VHQ0NxR1NNNDlBd0VIQTBJQUJFcFcwQlQrQW9DSDF3WnkKc1VjUjYzK2tXQ3FtU0NOVUo5Z1RTWnljajc3bmhSTVpwRHJPQU9XN2prRy9hVG9JOTlVRVdnT0N2VlVFZFk5YQpWZ3NpUGlhalNEQkdNQTRHQTFVZER3RUIvd1FFQXdJRm9EQVRCZ05WSFNVRUREQUtCZ2dyQmdFRkJRY0RBakFmCkJnTlZIU01FR0RBV2dCUlBzdVROVW01NHlGZ1ZvbXdkUFFnZXJGS1R5REFLQmdncWhrak9QUVFEQWdOSkFEQkcKQWlFQW5OS21uZzlnSlBncVJNcDdDRUU3TVltNTY1T054RklxaFZWWUVBVVNqNDRDSVFDc2dwTlN4Q2xuTDVlWgp3eTFYM2l1MXpLZzU2Q20wblk3aitTNjBIUHE2c1E9PQotLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tCi0tLS0tQkVHSU4gQ0VSVElGSUNBVEUtLS0tLQpNSUlCZHpDQ0FSMmdBd0lCQWdJQkFEQUtCZ2dxaGtqT1BRUURBakFqTVNFd0h3WURWUVFEREJock0zTXRZMnhwClpXNTBMV05oUURFM05ERXpOREV5TVRJd0hoY05NalV3TXpBM01EazFNek15V2hjTk16VXdNekExTURrMU16TXkKV2pBak1TRXdId1lEVlFRRERCaHJNM010WTJ4cFpXNTBMV05oUURFM05ERXpOREV5TVRJd1dUQVRCZ2NxaGtqTwpQUUlCQmdncWhrak9QUU1CQndOQ0FBU0VITTc2bURNTVZJOFZRRnVPL2N1RGNzbjJYbXZoZHRidGdMU2ZFQ2ozCm44VTR1QnNka1B5dVZvdFlpOG5kU1plNzlrRk45a1MwelM4dHV5YzZiWDVabzBJd1FEQU9CZ05WSFE4QkFmOEUKQkFNQ0FxUXdEd1lEVlIwVEFRSC9CQVV3QXdFQi96QWRCZ05WSFE0RUZnUVVUN0xrelZKdWVNaFlGYUpzSFQwSQpIcXhTazhnd0NnWUlLb1pJemowRUF3SURTQUF3UlFJaEFNOVlDNEtmKy8wSyszaGlOQzBlaXlHWmwwZVJxeUZkClZXRXZpYXlMR0tRNUFpQTdya0d6QmlMMkNoU3pSOUdkQzVycVBCMi95T2s4Qml3SDF1VHM0TFJqTEE9PQotLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tCg=="


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
        return user_identifier != "UNAUTHORIZED"

    async def is_usage_limit_exceeded(
        self, cluster_id: str
    ) -> UsageExceedReport | None:
        """Check if the token usage limit is exceeded for the given cluster_id."""
        if cluster_id == "EXCEEDED":
            return UsageExceedReport(
                cluster_id=cluster_id,
                token_limit=1000,
                total_tokens_used=1000,
                reset_seconds_left=60,
            )
        return None

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
            # should work when client certificate is provided.
            {
                "X-Client-Certificate-Data": SAMPLE_CLIENT_CERTIFICATE_DATA,
                "X-Client-Key-Data": "non-empty-client-key-data",
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
        (
            {
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            3,
            {
                "query": "should return error when k8s auth headers are missing",
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "my-pod",
                "namespace": "default",
            },
            {"status_code": 422, "content-type": "application/json"},
        ),
        (
            {
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
                "X-Client-Certificate-Data": SAMPLE_CLIENT_CERTIFICATE_DATA,
            },
            3,
            {
                "query": "should return error when k8s X-Client-Key-Data auth header is missing",
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "my-pod",
                "namespace": "default",
            },
            {"status_code": 422, "content-type": "application/json"},
        ),
        (
            {
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
                "X-Client-Key-Data": "non-empty-client-key-data",
            },
            3,
            {
                "query": "should return error when k8s X-Client-Certificate-Data auth header is missing",
                "resource_kind": "Pod",
                "resource_api_version": "v1",
                "resource_name": "my-pod",
                "namespace": "default",
            },
            {"status_code": 422, "content-type": "application/json"},
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
        b'"To create an API Rule in Kyma to expose a service externally", "tasks": []}, "error": null}}\n'
        in content
    )
    assert (
        b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"content": '
        b'"To create a kubernetes deployment", "tasks": []}, "error": null}}\n'
        in content
    )
    assert (
        b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"content'
        b'": "To create an API Rule in Kyma to expose a service externally", "tasks": '
        b'[]}, "error": null}}\n{"event": "agent_action", "data": {"agent": "KubernetesAgent", "an'
        b'swer": {"content": "To create a kubernetes deployment", "tasks": []}, "error": null}}\n'
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
            "should successfully initialize a conversation when client certificate is provided",
            {
                "X-Client-Certificate-Data": SAMPLE_CLIENT_CERTIFICATE_DATA,
                "X-Client-Key-Data": "non-empty-client-key-data",
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
                            "loc": ["header", "x-cluster-certificate-authority-data"],
                            "msg": "Field required",
                            "input": None,
                        },
                    ]
                },
            },
        ),
        (
            "should return error when k8s X-Client-Key-Data header is missing",
            {
                "X-Client-Certificate-Data": SAMPLE_CLIENT_CERTIFICATE_DATA,
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
                "status_code": 422,
                "content-type": "application/json",
                "body": {
                    "detail": "Either x-k8s-authorization header or x-client-certificate-data and x-client-key-data headers are required."
                },
            },
        ),
        (
            "should return error when k8s X-Client-Certificate-Data header is missing",
            {
                "X-Client-Key-Data": "non-empty-client-key-data",
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
                "status_code": 422,
                "content-type": "application/json",
                "body": {
                    "detail": "Either x-k8s-authorization header or x-client-certificate-data and x-client-key-data headers are required."
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
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
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
            # should successfully return follow-up questions when client certificate is provided.
            {
                "X-Client-Certificate-Data": SAMPLE_CLIENT_CERTIFICATE_DATA,
                "X-Client-Key-Data": "non-empty-client-key-data",
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
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
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
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
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
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
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            "a8172829-7f6c-4c76-aa16-e91edc7a14c8",
            None,
            {
                "status_code": ERROR_RATE_LIMIT_CODE,
                "content-type": "application/json",
                "body": {
                    "detail": {
                        "current_usage": 1000,
                        "error": "Rate limit exceeded",
                        "limit": 1000,
                        "message": "Daily token limit of 1000 exceeded for this cluster",
                        "time_remaining_seconds": 60,
                    },
                },
            },
        ),
        (
            # should return error when k8s headers are missing.
            {},
            "a8172829-7f6c-4c76-aa16-e91edc7a14c8",
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
                            "loc": ["header", "x-cluster-certificate-authority-data"],
                            "msg": "Field required",
                            "input": None,
                        },
                    ]
                },
            },
        ),
        (
            # "should return error when k8s X-Client-Key-Data header is missing",
            {
                "X-Client-Certificate-Data": SAMPLE_CLIENT_CERTIFICATE_DATA,
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            "a8172829-7f6c-4c76-aa16-e91edc7a14c8",
            None,
            {
                "status_code": 422,
                "content-type": "application/json",
                "body": {
                    "detail": "Either x-k8s-authorization header or x-client-certificate-data and x-client-key-data headers are required."
                },
            },
        ),
        (
            # "should return error when k8s X-Client-Certificate-Data header is missing",
            {
                "X-Client-Key-Data": "non-empty-client-key-data",
                "x-cluster-url": "https://api.k8s.example.com",
                "x-cluster-certificate-authority-data": "non-empty-ca-data",
            },
            "a8172829-7f6c-4c76-aa16-e91edc7a14c8",
            None,
            {
                "status_code": 422,
                "content-type": "application/json",
                "body": {
                    "detail": "Either x-k8s-authorization header or x-client-certificate-data and x-client-key-data headers are required."
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
    "cluster_url, usage_report, expected_exception",
    [
        (
            "https://api.k8s-id.example.com",
            None,
            None,
        ),
        (
            "https://api.k8s-id.example.com",
            UsageExceedReport(
                cluster_id="k8s-id",
                token_limit=1000,
                total_tokens_used=1000,
                reset_seconds_left=60,
            ),
            HTTPException,
        ),
    ],
)
async def test_check_token_usage(cluster_url, usage_report, expected_exception):
    # Mock the conversation_service
    mock_conversation_service = Mock()
    mock_conversation_service.is_usage_limit_exceeded = AsyncMock(
        return_value=usage_report
    )

    if expected_exception:
        with pytest.raises(expected_exception):
            await check_token_usage(cluster_url, mock_conversation_service)
    else:
        await check_token_usage(cluster_url, mock_conversation_service)
        mock_conversation_service.is_usage_limit_exceeded.assert_called_once_with(
            "k8s-id"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_description, conversation_id, token, certificate_data, user_identifier, is_authorized, expected_exception",
    [
        (
            "valid token, user authorized",
            "conversation1",
            jwt.encode({"sub": "user1"}, "secret", algorithm="HS256"),
            None,
            "user1",
            True,
            None,
        ),
        (
            "valid token, user not authorized",
            "conversation2",
            jwt.encode({"sub": "user2"}, "secret", algorithm="HS256"),
            None,
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
            None,
            HTTPException,
        ),
        (
            "valid client certificate, user authorized",
            "conversation1",
            None,
            SAMPLE_CLIENT_CERTIFICATE_DATA,
            "system:admin",
            True,
            None,
        ),
        (
            "invalid client certificate",
            "conversation3",
            None,
            "invalid-client-certificate",
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
    certificate_data,
    user_identifier,
    is_authorized,
    expected_exception,
):
    # given
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url="https://api.k8s.example.com",
        x_cluster_certificate_authority_data="non-empty-ca-data",
        x_k8s_authorization=token,
        x_client_certificate_data=certificate_data,
        x_client_key_data="non-empty-client-key-data",
    )

    # Mock the conversation_service
    mock_conversation_service = Mock()
    mock_conversation_service.authorize_user = AsyncMock(return_value=is_authorized)

    # when / then
    if expected_exception or not is_authorized:
        with pytest.raises(expected_exception):
            await authorize_user(
                conversation_id, k8s_auth_headers, mock_conversation_service
            )
    else:
        await authorize_user(
            conversation_id, k8s_auth_headers, mock_conversation_service
        )
        mock_conversation_service.authorize_user.assert_called_once_with(
            conversation_id, user_identifier
        )
