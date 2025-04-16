import datetime
import re

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from langchain_core.messages import BaseMessage, HumanMessage

from utils import utils
from utils.utils import (
    JWT_TOKEN_EMAIL,
    JWT_TOKEN_SERVICE_ACCOUNT,
    JWT_TOKEN_SUB,
    create_session_id,
    get_user_identifier_from_client_certificate,
    get_user_identifier_from_token,
    parse_k8s_token, to_sequence_messages,
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
            "user123",
            None,
        ),
        (
            "valid token with email",
            {JWT_TOKEN_EMAIL: "user@example.com"},
            "user@example.com",
            None,
        ),
        (
            "valid token with service account name",
            {JWT_TOKEN_SERVICE_ACCOUNT: "service-account"},
            "service-account",
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
def test_get_user_identifier_from_token(
    test_description, token_payload, expected_result, expected_exception
):
    token = jwt.encode(token_payload, "secret", algorithm="HS256")
    if expected_exception:
        with pytest.raises(
            expected_exception, match="Failed to get user identifier from token"
        ):
            get_user_identifier_from_token(token)
    else:
        user_identifier = get_user_identifier_from_token(token)
        assert user_identifier == expected_result, test_description


# Sample PEM certificates for testing
def generate_pem_cert(common_name: str, serial_number: str) -> bytes:
    # Generate a private key
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )

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
        .not_valid_after(
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365)
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    # Serialize the certificate to PEM format
    pem_cert = cert.public_bytes(Encoding.PEM)
    return pem_cert


# Test cases
@pytest.mark.parametrize(
    "client_certificate_data, expected_user_identifier, expected_error",
    [
        # Test case 1: Certificate with Common Name
        (
            generate_pem_cert("test_user", "12345"),
            "test_user",
            None,
        ),
        # Test case 2: Certificate without Common Name but with serial number
        (
            generate_pem_cert("", "67890"),
            "67890",
            None,
        ),
        # Test case 3: Invalid certificate data (e.g., not a valid PEM)
        (
            b"Invalid certificate data",
            "",
            ValueError,
        ),
    ],
)
def test_get_user_identifier_from_client_certificate(
    client_certificate_data, expected_user_identifier, expected_error
):
    if expected_error:
        with pytest.raises(ValueError):
            get_user_identifier_from_client_certificate(client_certificate_data)
    else:
        assert (
            get_user_identifier_from_client_certificate(client_certificate_data)
            == expected_user_identifier
        )


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
