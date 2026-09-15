import re
from unittest.mock import AsyncMock, Mock

import pytest

from agents.common.data import Message
from agents.common.utils import get_relevant_context_from_k8s_cluster
from services.data_sanitizer import DataSanitizer
from services.k8s import IK8sClient
from utils import utils
from utils.exceptions import K8sClientError
from utils.utils import create_session_id

UUID4_LENGTH = 32
UUID4_FORMAT_REGEX = "^[0-9a-f]{32}$"


def test_create_session_id():
    # when
    session_id = create_session_id()

    # then
    assert len(session_id) == UUID4_LENGTH
    # assert using regex the format of the UUID.
    assert re.match(UUID4_FORMAT_REGEX, session_id) is not None


@pytest.mark.parametrize(
    "input_data, expected_output",
    (
        ("", True),
        (" ", True),
        ("  ", True),
        (None, True),
        ("  a  ", False),
        ("a", False),
        ("a ", False),
        (" a", False),
    ),
)
def test_is_empty_str(input_data, expected_output):
    assert utils.is_empty_str(input_data) == expected_output


@pytest.mark.parametrize(
    "input_data, expected_output",
    (
        ("", False),
        (" ", False),
        ("  ", False),
        (None, False),
        ("  a  ", True),
        ("a", True),
        ("a ", True),
        (" a", True),
    ),
)
def test_is_non_empty_str(input_data, expected_output):
    assert utils.is_non_empty_str(input_data) == expected_output


@pytest.fixture
def mock_k8s_client():
    """Create a mock K8s client"""
    client = Mock(spec=IK8sClient)
    client.get_data_sanitizer.return_value = DataSanitizer()
    client.list_not_running_pods = Mock(return_value=[])
    client.list_nodes_metrics = AsyncMock(return_value=[])
    client.list_k8s_warning_events = Mock(return_value=[])
    client.describe_resource = Mock(return_value={})
    client.list_k8s_events_for_resource = Mock(return_value=[])
    # `get_namespace` is awaited before fetching warning events for a namespace
    # overview; by default the namespace exists.
    client.get_namespace = AsyncMock(return_value={"metadata": {"name": "default"}})
    return client


@pytest.mark.parametrize(
    "input_context,expected_patterns",
    [
        # Test password sanitization
        (
            "database_config:\n  password: super_secret_123\n  host: localhost",
            ["password={{REDACTED}}", "super_secret_123"],
        ),
        # Test API key sanitization
        ("api_key: abc123xyz789\nservice: my-service", ["api_key={{REDACTED}}", "abc123xyz789"]),
        # Test secret key sanitization
        ("secret-key=mysecretvalue\nanother_field=value", ["secret_key={{REDACTED}}", "mysecretvalue"]),
        # Test access token sanitization
        (
            "access_token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\nuser: admin",
            ["access_token={{REDACTED}}", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"],
        ),
        # Test Bearer token sanitization
        (
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            ["Bearer {{REDACTED}}", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"],
        ),
        # Test Basic auth sanitization
        ("Authorization: Basic dXNlcjpwYXNzd29yZA==", ["Authorization: Basic {{REDACTED}}", "dXNlcjpwYXNzd29yZA=="]),
        # Test username sanitization
        ("username: admin_user\npassword: secret", ["username={{REDACTED}}", "password={{REDACTED}}"]),
        # Test user_name sanitization
        ("user_name=john.doe\nemail=test@example.com", ["user_name={{REDACTED}}", "john.doe"]),
        # Test multiple credentials in same context
        (
            "password: pass123\napi_key: key456\nsecret_key: secret789",
            ["password={{REDACTED}}", "api_key={{REDACTED}}", "secret_key={{REDACTED}}"],
        ),
        # Test case insensitivity
        ("PASSWORD: MyPassword\nAPI_KEY: MyApiKey", ["password={{REDACTED}}", "api_key={{REDACTED}}"]),
    ],
)
@pytest.mark.asyncio
async def test_cluster_overview_sanitization(mock_k8s_client, input_context, expected_patterns):
    """Test sanitization for cluster overview scenario"""
    # Setup
    message = Message(
        query="test",
        namespace="",
        resource_kind="cluster",
        resource_name="test-name",
        resource_api_version="v1",
    )
    mock_k8s_client.list_not_running_pods.return_value = [{"data": input_context}]

    # Execute
    result = await get_relevant_context_from_k8s_cluster(message, mock_k8s_client)

    # Verify sanitization occurred
    assert mock_k8s_client.get_data_sanitizer.called

    # Verify sensitive data is redacted
    assert "{{REDACTED}}" in result
    for pattern in expected_patterns[1:]:  # Skip the REDACTED pattern
        assert pattern not in result, f"Sensitive data '{pattern}' should be redacted"


@pytest.mark.parametrize(
    "input_context,expected_patterns",
    [
        # Test YAML formatted secrets
        (
            """
                apiVersion: v1
                kind: Secret
                metadata:
                  name: my-secret
                data:
                  password: cGFzc3dvcmQxMjM=
                  api_key: YXBpa2V5NDU2
                """,
            ["password={{REDACTED}}", "api_key={{REDACTED}}"],
        ),
        # Test configmap with credentials (bad practice but happens)
        (
            """
                kind: ConfigMap
                data:
                  config.yaml: |
                    username: service_account
                    secret-key: my_secret_value
                """,
            ["username={{REDACTED}}", "secret_key={{REDACTED}}"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_namespace_overview_sanitization(mock_k8s_client, input_context, expected_patterns):
    """Test sanitization for namespace overview scenario"""
    # Setup
    message = Message(
        query="test",
        namespace="default",
        resource_kind="namespace",
        resource_name="",
        resource_api_version="",
    )
    mock_k8s_client.list_k8s_warning_events.return_value = [{"message": input_context}]

    # Execute
    result = await get_relevant_context_from_k8s_cluster(message, mock_k8s_client)

    # Verify
    assert mock_k8s_client.get_data_sanitizer.called
    assert "{{REDACTED}}" in result
    # `get_namespace` must be awaited to verify the namespace exists before
    # fetching warning events.
    mock_k8s_client.get_namespace.assert_awaited_once_with("default")
    assert mock_k8s_client.list_k8s_warning_events.called


@pytest.mark.parametrize(
    "namespace,namespace_exists,expected_result,expects_events_fetch",
    [
        (
            "missing-ns",
            False,
            "Namespace 'missing-ns' was not found in the cluster.",
            False,
        ),
        (
            "default",
            True,
            "Namespace 'default' exists, but no warning or error events were found.",
            True,
        ),
    ],
    ids=["namespace_does_not_exist", "namespace_exists_no_events"],
)
@pytest.mark.asyncio
async def test_namespace_overview(mock_k8s_client, namespace, namespace_exists, expected_result, expects_events_fetch):
    """Namespace overview should:
    - return a not-found message and skip fetching warning events when
      `get_namespace` raises K8sClientError with status 404;
    - return a no-events placeholder when the namespace exists but has no
      warning events.
    """
    # Setup
    message = Message(
        query="test",
        namespace=namespace,
        resource_kind="namespace",
        resource_name="",
        resource_api_version="",
    )
    if not namespace_exists:
        mock_k8s_client.get_namespace.side_effect = K8sClientError("namespace not found", status_code=404)
    mock_k8s_client.list_k8s_warning_events.return_value = []

    # Execute
    result = await get_relevant_context_from_k8s_cluster(message, mock_k8s_client)

    # Verify
    mock_k8s_client.get_namespace.assert_awaited_once_with(namespace)
    assert result == expected_result
    if expects_events_fetch:
        assert mock_k8s_client.list_k8s_warning_events.called
    else:
        mock_k8s_client.list_k8s_warning_events.assert_not_called()


@pytest.mark.parametrize(
    "resource_data,event_data,expected_redactions",
    [
        # Test service with auth headers
        ({"metadata": {"annotations": {"auth": "Bearer my_token_here"}}}, [], ["my_token_here"]),
    ],
)
@pytest.mark.asyncio
async def test_resource_description_sanitization(mock_k8s_client, resource_data, event_data, expected_redactions):
    """Test sanitization for specific resource description"""
    # Setup
    message = Message(
        query="test",
        namespace="",
        resource_kind="test-kind",
        resource_name="test-name",
        resource_api_version="v1",
    )
    mock_k8s_client.describe_resource.return_value = resource_data
    mock_k8s_client.list_k8s_events_for_resource.return_value = event_data

    # Execute
    result = await get_relevant_context_from_k8s_cluster(message, mock_k8s_client)

    # Verify
    assert mock_k8s_client.get_data_sanitizer.called
    for sensitive_value in expected_redactions:
        assert sensitive_value not in result, f"Sensitive data '{sensitive_value}' should be redacted"
