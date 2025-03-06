import re

import jwt
import pytest

from utils import utils
from utils.utils import (
    JWT_TOKEN_EMAIL,
    JWT_TOKEN_SERVICE_ACCOUNT,
    JWT_TOKEN_SUB,
    create_session_id,
    get_user_identifier_from_token,
    parse_k8s_token,
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
