import datetime
import re
from unittest.mock import Mock, AsyncMock

from agents.common.data import Message
import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from langchain_core.messages import HumanMessage

from agents.common.utils import get_relevant_context_from_k8s_cluster
from services.data_sanitizer import DataSanitizer
from services.k8s import IK8sClient
from utils import utils
from utils.utils import (
    JWT_TOKEN_EMAIL,
    JWT_TOKEN_SERVICE_ACCOUNT,
    JWT_TOKEN_SUB,
    create_session_id,
    generate_sha256_hash,
    get_user_identifier_from_client_certificate,
    get_user_identifier_from_token,
    parse_k8s_token,
    to_sequence_messages,
)

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


@pytest.mark.parametrize(
    "test_description, token, expected_result, expected_exception",
    [
        (
            "valid token with sub",
            jwt.encode({"sub": "user123"}, "secret", algorithm="HS256"),
            {"sub": "user123"},
            None,
        ),
        (
            "invalid token",
            "invalid.token.here",
            None,
            ValueError,
        ),
        (
            "empty token",
            "",
            None,
            ValueError,
        ),
    ],
)
def test_parse_k8s_token(test_description, token, expected_result, expected_exception):
    if expected_exception:
        with pytest.raises(expected_exception, match="Failed to parse k8s token"):
            parse_k8s_token(token)
    else:
        decoded_token = parse_k8s_token(token)
        assert decoded_token == expected_result, test_description


@pytest.mark.parametrize(
    "test_description, token_payload, expected_result, expected_exception",
    [
        (
            "valid token with sub",
            {JWT_TOKEN_SUB: "user123"},
            "e606e38b0d8c19b24cf0ee3808183162ea7cd63ff7912dbb22b5e803286b4446",
            None,
        ),
        (
            "valid token with email",
            {JWT_TOKEN_EMAIL: "user@example.com"},
            "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514",
            None,
        ),
        (
            "valid token with service account name",
            {JWT_TOKEN_SERVICE_ACCOUNT: "service-account"},
            "eb358b69ae30c7bea54b497b6ab1bcffb613bcf1e82099e6bb082047df8b4965",
            None,
        ),
        (
            "invalid token with no user identifier",
            {"foo": "bar"},
            None,
            ValueError,
        ),
        (
            "empty token",
            {},
            None,
            ValueError,
        ),
    ],
)
def test_get_user_identifier_from_token(test_description, token_payload, expected_result, expected_exception):
    token = jwt.encode(token_payload, "secret", algorithm="HS256")
    if expected_exception:
        with pytest.raises(expected_exception, match="Failed to get user identifier from token"):
            get_user_identifier_from_token(token)
    else:
        user_identifier = get_user_identifier_from_token(token)
        assert user_identifier == expected_result, test_description


# Sample PEM certificates for testing
def generate_pem_cert(common_name: str, serial_number: str) -> bytes:
    # Generate a private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

    issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "test"),
        ]
    )

    subject = x509.Name([])
    if common_name:
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ]
        )

    # Build the certificate
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(int(serial_number))
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    # Serialize the certificate to PEM format
    pem_cert = cert.public_bytes(Encoding.PEM)
    return pem_cert


# Test cases
@pytest.mark.parametrize(
    "test_description, client_certificate_data, expected_user_identifier, expected_error",
    [
        (
            "Test case 1 Certificate with Common Name",
            # generated using generate_pem_cert("test_user", "12345")
            b"-----BEGIN CERTIFICATE-----\nMIICsjCCAZqgAwIBAgICMDkwDQYJKoZIhvcNAQELBQAwDzENMAsGA1UEAwwEdGVz\ndDAeFw0yNTA3MjgxNDQ3NDlaFw0yNjA3MjgxNDQ3NDlaMBQxEjAQBgNVBAMMCXRl\nc3RfdXNlcjCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJX9BZd2A76C\nZy2sBjjZIaIFO2lF59h3bcqw9k0GXt5d8Jo372Kw1MdT6DTHuSv63SEmM2slXy2Z\nDOGSZg9nyoh+yTLEO5XS21f9o53j89XQ/dSAX0QsYvwmTeHvnJAksEuKhRDWQXLy\nD50BcmMyaT8mPrAVg4OMIzcFfpl4wwBSv6ftLcdG0whe7f9e7ke69FNJy2f7VG8i\nt0zDBijxtNVxFkeWYgZDvvIJuTgoJNw1lRoAXEkbbqPa+y4B9ShcpZqhZd/yT8Jx\nenxf3pVWZwKxx2opvwRQJ2tlMqln5+FITX+qKriEA96XGOie+EUGBBFGabf/pLKn\nILHPKP8vaW0CAwEAAaMTMBEwDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsF\nAAOCAQEAX1r2GF8SVY9wey4bQ9Nn/1luSf60DMGUJfE8C/Lcq85MjpiAQ30qV/bb\nPOgNZ7LDISg5e06MP2ZCIqIhUMS6MfW/JX/g8XJo9RGgM3WWLhb43VesFb+SFi7Q\nKQ+LtvFlykaHyVmlLwnvnyG29vIt77cOngL9g5ESWAl7qGRa7pb2+w/YjLR5oOnU\nxqvtn8N2KAh1cwFslOi9IfgGEcwA+hd/rc6tlXDbmd8AZcWZo2pmBCYu+YZGSkGX\nTBIxLnQLRtaxwR8tENbb0x2PgiSK0cLAex86VOYlBNsb8Pt4FpSlupDFhKPtT0Va\nSUcAlZwnnepwKMSTCiTupOqi859+BA==\n-----END CERTIFICATE-----\n",
            "1160130875fda0812c99c5e3f1a03516471a6370c4f97129b221938eb4763e63",
            None,
        ),
        (
            "Test case 2 Certificate without Common Name but with serial number",
            # generated using generate_pem_cert("", "67890")
            b"-----BEGIN CERTIFICATE-----\nMIICnzCCAYegAwIBAgIDAQkyMA0GCSqGSIb3DQEBCwUAMA8xDTALBgNVBAMMBHRl\nc3QwHhcNMjUwNzI4MTQ0NzQ5WhcNMjYwNzI4MTQ0NzQ5WjAAMIIBIjANBgkqhkiG\n9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0KwcFwyPInr7IJfeH/15aSljGQjnSkPLoMun\nPqBv/fX2A7Ms/yoYOL6AwRzjZUhtq+qxQ5topKJPRbnk3US1vwv5CL32wxZIDbne\nDA0NWBqujtSSE3SdoA9TyW2wPj7RJVTuastrGZt9TAX4zuaIY3OeIUA99bHrckgn\nITUk+3mky5Bp6RvBdD/XlgcqtimBec2rETXnvk+hVOSLv1J/hem55cFNN16h6+El\nIRTo1ofVa7G+D3Slpgm0S5UZWoc/D133p0oL+9tqtWiZZcfJms4wlmFuVoYj+4AP\n3RFVsY58aTvTG51FoBQtODdvdF+gnVsc+T1BEavTNopHxERifwIDAQABoxMwETAP\nBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQCBGARgbIMGYnBiw1pV\n5AFji0g1L1YmsTJC6W69CAi6GihvtzRtHMyTu8dyMvObVYxonzJ4CSmhEA4z6X0i\n4mKCRmjgSa4XkGBfBFJkbuq2iMDQZECgcE+nSZJgSw/tFcyjuTuhysuBuk66xN4i\niLDiLV4Z5qLYfcYnIoIBis6xkOHT3ynS9GC9Dp5Gu5grVqUQYXsEeITldjHaz79O\n8imuqZe74QX2NmXizpwASGPNrTyCe4D5jZ6b7aDo9Pg9JPuIHOKP+fVZMSzyfbmj\nwKslFuEecN1ORnGNE8PoEv9itGh18bQ2gnewqxLxWTsDzq9N7KsRf2OBiIxgpV1j\naDxa\n-----END CERTIFICATE-----\n",
            "e2217d3e4e120c6a3372a1890f03e232b35ad659d71f7a62501a4ee204a3e66d",
            None,
        ),
        (
            "Test case 3: Invalid certificate data",
            b"Invalid certificate data",
            "",
            ValueError,
        ),
    ],
)
def test_get_user_identifier_from_client_certificate(
    test_description, client_certificate_data, expected_user_identifier, expected_error
):
    if expected_error:
        with pytest.raises(ValueError):
            get_user_identifier_from_client_certificate(client_certificate_data)
    else:
        assert get_user_identifier_from_client_certificate(client_certificate_data) == expected_user_identifier


@pytest.mark.parametrize(
    "test_description, input_data, expected_output, expected_exception",
    [
        # Test case 1: Single BaseMessage
        (
            "Single BaseMessage",
            HumanMessage("test message"),
            [HumanMessage("test message")],
            None,
        ),
        # Test case 2: List of BaseMessage
        (
            "List of BaseMessage",
            [HumanMessage("message 1"), HumanMessage("message 2")],
            [HumanMessage("message 1"), HumanMessage("message 2")],
            None,
        ),
        # Test case 3: Mixed list with invalid types
        (
            "Mixed list with invalid types",
            [HumanMessage("valid message"), "invalid message"],
            None,
            ValueError,
        ),
        # Test case 4: Empty list
        (
            "Empty list",
            [],
            [],
            None,
        ),
        # Test case 5: Invalid type (e.g., string)
        (
            "Invalid type (string)",
            "invalid message",
            None,
            ValueError,
        ),
        # Test case 6: List of strings
        (
            "List of strings",
            ["string1", "string2"],
            None,
            ValueError,
        ),
    ],
)
def test_to_sequence_messages(test_description, input_data, expected_output, expected_exception):
    if expected_exception:
        with pytest.raises(expected_exception, match="Unsupported message type"):
            to_sequence_messages(input_data)
    else:
        result = to_sequence_messages(input_data)
        assert result == expected_output, test_description


@pytest.mark.parametrize(
    "input_data, expected_hash",
    [
        ("hello", "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"),
        ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("123456", "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"),
        (
            "test string",
            "d5579c46dfcc7f18207013e65b44e4cb4e2c2298f4ac457ba8f82743f31e930b",
        ),
        (
            "test@email.com",
            "73062d872926c2a556f17b36f50e328ddf9bff9d403939bd14b6c3b7f5a33fc2",
        ),
        (
            "Person Name",
            "524540a60d1c748cbd8019a8702f5ba3e345168e590fe6460715af0f552c7083",
        ),
        (
            "UNAUTHORIZED",
            "87a5e00b7c0b4287fea96bbeabc05fdfdaacba5346b606366be40fbf3046cc9a",
        ),
    ],
)
def test_generate_sha256_hash(input_data, expected_hash):
    assert generate_sha256_hash(input_data) == expected_hash


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
    return client


@pytest.mark.parametrize(
    "input_context,expected_patterns",
    [
        # Test password sanitization
        (
                "database_config:\n  password: super_secret_123\n  host: localhost",
                ["password={{REDACTED}}", "super_secret_123"]
        ),
        # Test API key sanitization
        (
                "api_key: abc123xyz789\nservice: my-service",
                ["api_key={{REDACTED}}", "abc123xyz789"]
        ),
        # Test secret key sanitization
        (
                "secret-key=mysecretvalue\nanother_field=value",
                ["secret_key={{REDACTED}}", "mysecretvalue"]
        ),
        # Test access token sanitization
        (
                "access_token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\nuser: admin",
                ["access_token={{REDACTED}}", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"]
        ),
        # Test Bearer token sanitization
        (
                "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                ["Bearer {{REDACTED}}", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"]
        ),
        # Test Basic auth sanitization
        (
                "Authorization: Basic dXNlcjpwYXNzd29yZA==",
                ["Authorization: Basic {{REDACTED}}", "dXNlcjpwYXNzd29yZA=="]
        ),
        # Test username sanitization
        (
                "username: admin_user\npassword: secret",
                ["username={{REDACTED}}", "password={{REDACTED}}"]
        ),
        # Test user_name sanitization
        (
                "user_name=john.doe\nemail=test@example.com",
                ["user_name={{REDACTED}}", "john.doe"]
        ),
        # Test multiple credentials in same context
        (
                "password: pass123\napi_key: key456\nsecret_key: secret789",
                ["password={{REDACTED}}", "api_key={{REDACTED}}", "secret_key={{REDACTED}}"]
        ),
        # Test case insensitivity
        (
                "PASSWORD: MyPassword\nAPI_KEY: MyApiKey",
                ["password={{REDACTED}}", "api_key={{REDACTED}}"]
        ),
    ],
)
@pytest.mark.asyncio
async def test_cluster_overview_sanitization(
        mock_k8s_client, input_context, expected_patterns
):
    """Test sanitization for cluster overview scenario"""
    # Setup
    message = Message(
                query="test",
                namespace="",
                resource_kind="test-kind",
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
                ["password={{REDACTED}}", "api_key={{REDACTED}}"]
        ),
        # Test environment variables
        (
                """
                env:
                  - name: DB_PASSWORD
                    value: db_pass_123
                  - name: API_KEY
                    value: api_key_456
                """,
                ["password={{REDACTED}}", "api_key={{REDACTED}}"]
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
                ["username={{REDACTED}}", "secret_key={{REDACTED}}"]
        ),
    ],
)
@pytest.mark.asyncio
async def test_namespace_overview_sanitization(
        mock_k8s_client, input_context, expected_patterns
):
    """Test sanitization for namespace overview scenario"""
    # Setup
    message = Message(
                query="test",
                namespace="",
                resource_kind="test-kind",
                resource_name="test-name",
                resource_api_version="v1",
            )
    mock_k8s_client.list_k8s_warning_events.return_value = [{"message": input_context}]

    # Execute
    result = await get_relevant_context_from_k8s_cluster(message, mock_k8s_client)

    # Verify
    assert mock_k8s_client.get_data_sanitizer.called
    assert "{{REDACTED}}" in result


@pytest.mark.parametrize(
    "resource_data,event_data,expected_redactions",
    [
        # Test pod with secrets
        (
                {
                    "spec": {
                        "containers": [{
                            "env": [
                                {"name": "PASSWORD", "value": "secret123"}
                            ]
                        }]
                    }
                },
                [{"message": "api-key: xyz789"}],
                ["secret123", "xyz789"]
        ),
        # Test service with auth headers
        (
                {
                    "metadata": {
                        "annotations": {
                            "auth": "Bearer my_token_here"
                        }
                    }
                },
                [],
                ["my_token_here"]
        ),
        # Test deployment with multiple secrets
        (
                {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [{
                                    "env": [
                                        {"name": "DB_PASSWORD", "value": "dbpass"},
                                        {"name": "API_KEY", "value": "apikey123"},
                                        {"name": "SECRET_KEY", "value": "secretkey456"}
                                    ]
                                }]
                            }
                        }
                    }
                },
                [],
                ["dbpass", "apikey123", "secretkey456"]
        ),
    ],
)
@pytest.mark.asyncio
async def test_resource_description_sanitization(
        mock_k8s_client, resource_data, event_data, expected_redactions
):
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
