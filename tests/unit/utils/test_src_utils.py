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

from utils import utils
from utils.utils import (
    JWT_TOKEN_EMAIL,
    JWT_TOKEN_SERVICE_ACCOUNT,
    JWT_TOKEN_SUB,
    create_session_id,
    get_user_identifier_from_client_certificate,
    get_user_identifier_from_token,
    parse_k8s_token,
)

UUID4_LENGTH = 32
UUID4_FORMAT_REGEX = "^[0-9a-f]{32}$"
SAMPLE_CLIENT_CERTIFICATE_DATA = "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJrakNDQVRlZ0F3SUJBZ0lJTmpJSzErZmhrZUF3Q2dZSUtvWkl6ajBFQXdJd0l6RWhNQjhHQTFVRUF3d1kKYXpOekxXTnNhV1Z1ZEMxallVQXhOelF4TXpReE1qRXlNQjRYRFRJMU1ETXdOekE1TlRNek1sb1hEVEkyTURNdwpOekE1TlRNek1sb3dNREVYTUJVR0ExVUVDaE1PYzNsemRHVnRPbTFoYzNSbGNuTXhGVEFUQmdOVkJBTVRESE41CmMzUmxiVHBoWkcxcGJqQlpNQk1HQnlxR1NNNDlBZ0VHQ0NxR1NNNDlBd0VIQTBJQUJFcFcwQlQrQW9DSDF3WnkKc1VjUjYzK2tXQ3FtU0NOVUo5Z1RTWnljajc3bmhSTVpwRHJPQU9XN2prRy9hVG9JOTlVRVdnT0N2VlVFZFk5YQpWZ3NpUGlhalNEQkdNQTRHQTFVZER3RUIvd1FFQXdJRm9EQVRCZ05WSFNVRUREQUtCZ2dyQmdFRkJRY0RBakFmCkJnTlZIU01FR0RBV2dCUlBzdVROVW01NHlGZ1ZvbXdkUFFnZXJGS1R5REFLQmdncWhrak9QUVFEQWdOSkFEQkcKQWlFQW5OS21uZzlnSlBncVJNcDdDRUU3TVltNTY1T054RklxaFZWWUVBVVNqNDRDSVFDc2dwTlN4Q2xuTDVlWgp3eTFYM2l1MXpLZzU2Q20wblk3aitTNjBIUHE2c1E9PQotLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tCi0tLS0tQkVHSU4gQ0VSVElGSUNBVEUtLS0tLQpNSUlCZHpDQ0FSMmdBd0lCQWdJQkFEQUtCZ2dxaGtqT1BRUURBakFqTVNFd0h3WURWUVFEREJock0zTXRZMnhwClpXNTBMV05oUURFM05ERXpOREV5TVRJd0hoY05NalV3TXpBM01EazFNek15V2hjTk16VXdNekExTURrMU16TXkKV2pBak1TRXdId1lEVlFRRERCaHJNM010WTJ4cFpXNTBMV05oUURFM05ERXpOREV5TVRJd1dUQVRCZ2NxaGtqTwpQUUlCQmdncWhrak9QUU1CQndOQ0FBU0VITTc2bURNTVZJOFZRRnVPL2N1RGNzbjJYbXZoZHRidGdMU2ZFQ2ozCm44VTR1QnNka1B5dVZvdFlpOG5kU1plNzlrRk45a1MwelM4dHV5YzZiWDVabzBJd1FEQU9CZ05WSFE4QkFmOEUKQkFNQ0FxUXdEd1lEVlIwVEFRSC9CQVV3QXdFQi96QWRCZ05WSFE0RUZnUVVUN0xrelZKdWVNaFlGYUpzSFQwSQpIcXhTazhnd0NnWUlLb1pJemowRUF3SURTQUF3UlFJaEFNOVlDNEtmKy8wSyszaGlOQzBlaXlHWmwwZVJxeUZkClZXRXZpYXlMR0tRNUFpQTdya0d6QmlMMkNoU3pSOUdkQzVycVBCMi95T2s4Qml3SDF1VHM0TFJqTEE9PQotLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tCg=="


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
        assert decoded_token == expected_result


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
        assert user_identifier == expected_result


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
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
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
