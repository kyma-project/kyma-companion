"""Unit tests for services/encryption.py."""

import base64
import os
import re
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from services.encryption import Encryption
from services.encryption_cache import IEncryptionCache

_ECDH_CURVE = ec.SECP256R1()
_HKDF_INFO = b"ecdh-key-exchange"
_AES_GCM_NONCE_SIZE = 12
_AES_KEY_SIZE = 32


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ec_public_key_b64(key: EllipticCurvePrivateKey) -> str:
    """Encode the uncompressed public point of an EC key as base64."""
    return base64.b64encode(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)).decode()


def _make_encrypted_payload(
    server_private_key: EllipticCurvePrivateKey,
    plaintext: bytes,
) -> tuple[str, str, str, str]:
    """Simulate client-side ECDH + AES-256-GCM encryption.

    Returns (encrypted_key_b64, iv_b64, encrypted_data_b64, client_public_key_b64).
    """
    client_key = ec.generate_private_key(_ECDH_CURVE)

    shared_secret = client_key.exchange(ec.ECDH(), server_private_key.public_key())
    shared_key = HKDF(algorithm=SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(shared_secret)

    aes_key = os.urandom(32)
    key_nonce = os.urandom(_AES_GCM_NONCE_SIZE)
    encrypted_key = base64.b64encode(key_nonce + AESGCM(shared_key).encrypt(key_nonce, aes_key, None)).decode()

    iv = os.urandom(_AES_GCM_NONCE_SIZE)
    encrypted_data = base64.b64encode(AESGCM(aes_key).encrypt(iv, plaintext, None)).decode()

    return (
        encrypted_key,
        base64.b64encode(iv).decode(),
        encrypted_data,
        _ec_public_key_b64(client_key),
    )


# ---------------------------------------------------------------------------
# Module-level test vectors (computed once per test-session / worker process)
# ---------------------------------------------------------------------------

_SERVER_KEY = ec.generate_private_key(_ECDH_CURVE)

_PLAINTEXT = b'{"x_cluster_url": "https://test.example.com"}'
_VALID_ENCRYPTED_KEY, _VALID_IV, _VALID_ENCRYPTED_DATA, _CLIENT_PUBLIC_KEY_B64 = _make_encrypted_payload(
    _SERVER_KEY, _PLAINTEXT
)

_CORRUPTED_ENCRYPTED_KEY = base64.b64encode(os.urandom(60)).decode()

# Separate client key whose private side is accessible, used for testing
# _derive_shared_key and _decrypt_aes_key in isolation.
_CLIENT_KEY_HELPER = ec.generate_private_key(_ECDH_CURVE)
_CLIENT_PUBLIC_KEY_HELPER_B64 = _ec_public_key_b64(_CLIENT_KEY_HELPER)
_EXPECTED_SHARED_KEY = HKDF(algorithm=SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(
    _CLIENT_KEY_HELPER.exchange(ec.ECDH(), _SERVER_KEY.public_key())
)

_HELPER_AES_KEY = os.urandom(32)
_HELPER_KEY_NONCE = os.urandom(_AES_GCM_NONCE_SIZE)
_ENCRYPTED_AES_KEY_B64 = base64.b64encode(
    _HELPER_KEY_NONCE + AESGCM(_EXPECTED_SHARED_KEY).encrypt(_HELPER_KEY_NONCE, _HELPER_AES_KEY, None)
).decode()
_CORRUPTED_AES_KEY_B64 = base64.b64encode(os.urandom(60)).decode()

_HELPER_PLAINTEXT = b"helper test plaintext"
_HELPER_DATA_IV = os.urandom(_AES_GCM_NONCE_SIZE)
_HELPER_DATA_IV_B64 = base64.b64encode(_HELPER_DATA_IV).decode()
_ENCRYPTED_HELPER_DATA_B64 = base64.b64encode(
    AESGCM(_HELPER_AES_KEY).encrypt(_HELPER_DATA_IV, _HELPER_PLAINTEXT, None)
).decode()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEncryption:
    @pytest.mark.parametrize(
        "test_case, private_key, expected_error, expected_error_msg",
        [
            pytest.param(
                "valid EC P-256 private key is accepted",
                _SERVER_KEY,
                None,
                None,
                id="valid_ec_key",
            ),
            pytest.param(
                "None raises TypeError",
                None,
                TypeError,
                "private_key is not an EC private key",
                id="none",
            ),
            pytest.param(
                "string raises TypeError",
                "not-an-ec-key",
                TypeError,
                "private_key is not an EC private key",
                id="string",
            ),
            pytest.param(
                "integer raises TypeError",
                42,
                TypeError,
                "private_key is not an EC private key",
                id="integer",
            ),
        ],
    )
    def test_init(
        self,
        test_case: str,
        private_key: object,
        expected_error: type[Exception] | None,
        expected_error_msg: str | None,
    ):
        mock_cache = AsyncMock(spec=IEncryptionCache)

        if expected_error is None:
            # Given / When:
            enc = Encryption(private_key, mock_cache)

            # Then:
            assert isinstance(enc._private_key, EllipticCurvePrivateKey), test_case
        else:
            match = re.escape(expected_error_msg) if expected_error_msg else None
            with pytest.raises(expected_error, match=match):
                Encryption(private_key, mock_cache)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case, client_public_key, nonce_allowed, encrypted_key, iv, encrypted_data, expected_result, expected_error, expected_error_msg",
        [
            pytest.param(
                "valid payload is decrypted and the original plaintext is returned",
                _CLIENT_PUBLIC_KEY_B64,
                True,
                _VALID_ENCRYPTED_KEY,
                _VALID_IV,
                _VALID_ENCRYPTED_DATA,
                _PLAINTEXT,
                None,
                None,
                id="success",
            ),
            pytest.param(
                "raises ValueError when the client public key is not found in cache",
                None,
                True,
                _VALID_ENCRYPTED_KEY,
                _VALID_IV,
                _VALID_ENCRYPTED_DATA,
                None,
                ValueError,
                "Client public key not found: session-123",
                id="client_key_not_found",
            ),
            pytest.param(
                "raises ValueError when the nonce was already used outside the replay window",
                _CLIENT_PUBLIC_KEY_B64,
                False,
                _VALID_ENCRYPTED_KEY,
                _VALID_IV,
                _VALID_ENCRYPTED_DATA,
                None,
                ValueError,
                "Replay attack detected: nonce already used outside the allowed window",
                id="replay_attack",
            ),
            pytest.param(
                "raises ValueError when the IV is not 12 bytes",
                _CLIENT_PUBLIC_KEY_B64,
                True,
                _VALID_ENCRYPTED_KEY,
                base64.b64encode(b"short").decode(),
                _VALID_ENCRYPTED_DATA,
                None,
                ValueError,
                "IV must be 12 bytes, got 5",
                id="invalid_iv_length",
            ),
            pytest.param(
                "raises an exception when encrypted_key cannot be decrypted",
                _CLIENT_PUBLIC_KEY_B64,
                True,
                _CORRUPTED_ENCRYPTED_KEY,
                _VALID_IV,
                _VALID_ENCRYPTED_DATA,
                None,
                Exception,
                None,
                id="corrupted_encrypted_key",
            ),
        ],
    )
    async def test_decrypt(
        self,
        test_case: str,
        client_public_key: str | None,
        nonce_allowed: bool,
        encrypted_key: str,
        iv: str,
        encrypted_data: str,
        expected_result: bytes | None,
        expected_error: type[Exception] | None,
        expected_error_msg: str | None,
    ):
        # Given:
        mock_cache = AsyncMock(spec=IEncryptionCache)
        mock_cache.get_client_public_key.return_value = client_public_key
        mock_cache.is_nonce_allowed.return_value = nonce_allowed

        enc = Encryption(_SERVER_KEY, mock_cache)

        if expected_error is None:
            # When:
            result = await enc.decrypt(encrypted_key, iv, "session-123", encrypted_data)

            # Then:
            assert result == expected_result, test_case
        else:
            match = re.escape(expected_error_msg) if expected_error_msg else None
            with pytest.raises(expected_error, match=match):
                await enc.decrypt(encrypted_key, iv, "session-123", encrypted_data)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case, cache_return_value, expected_result",
        [
            pytest.param(
                "returns the public key string when the cache contains the session key",
                "some-public-key",
                "some-public-key",
                id="key_found",
            ),
            pytest.param(
                "returns None when the session key is absent from the cache",
                None,
                None,
                id="key_not_found",
            ),
        ],
    )
    async def test_get_client_public_key(
        self,
        test_case: str,
        cache_return_value: str | None,
        expected_result: str | None,
    ):
        # Given:
        mock_cache = AsyncMock(spec=IEncryptionCache)
        mock_cache.get_client_public_key.return_value = cache_return_value
        enc = Encryption(_SERVER_KEY, mock_cache)

        # When:
        result = await enc._get_client_public_key("session-123")

        # Then:
        assert result == expected_result, test_case
        mock_cache.get_client_public_key.assert_called_once_with("session-123")

    @pytest.mark.parametrize(
        "test_case, client_public_key_b64, expected_result, expected_error",
        [
            pytest.param(
                "valid client public key produces the correct 32-byte shared key",
                _CLIENT_PUBLIC_KEY_HELPER_B64,
                _EXPECTED_SHARED_KEY,
                None,
                id="valid_key",
            ),
            pytest.param(
                "invalid base64 raises an exception",
                "not-valid-base64!!!",
                None,
                Exception,
                id="invalid_base64",
            ),
            pytest.param(
                "valid base64 but not a valid EC point raises an exception",
                base64.b64encode(b"not a valid ec point").decode(),
                None,
                Exception,
                id="invalid_ec_point",
            ),
        ],
    )
    def test_derive_shared_key(
        self,
        test_case: str,
        client_public_key_b64: str,
        expected_result: bytes | None,
        expected_error: type[Exception] | None,
    ):
        enc = Encryption(_SERVER_KEY, AsyncMock(spec=IEncryptionCache))

        if expected_error is None:
            # When:
            result = enc._derive_shared_key(client_public_key_b64)

            # Then:
            assert result == expected_result, test_case
            assert len(result) == _AES_KEY_SIZE, test_case
        else:
            with pytest.raises(expected_error):
                enc._derive_shared_key(client_public_key_b64)

    @pytest.mark.parametrize(
        "test_case, encrypted_key_b64, shared_key, expected_result, expected_error",
        [
            pytest.param(
                "valid encrypted AES key is decrypted to the original key bytes",
                _ENCRYPTED_AES_KEY_B64,
                _EXPECTED_SHARED_KEY,
                _HELPER_AES_KEY,
                None,
                id="valid",
            ),
            pytest.param(
                "corrupted ciphertext raises an exception",
                _CORRUPTED_AES_KEY_B64,
                _EXPECTED_SHARED_KEY,
                None,
                Exception,
                id="corrupted_ciphertext",
            ),
            pytest.param(
                "invalid base64 raises an exception",
                "not-valid-base64!!!",
                _EXPECTED_SHARED_KEY,
                None,
                Exception,
                id="invalid_base64",
            ),
        ],
    )
    def test_decrypt_aes_key(
        self,
        test_case: str,
        encrypted_key_b64: str,
        shared_key: bytes,
        expected_result: bytes | None,
        expected_error: type[Exception] | None,
    ):
        enc = Encryption(_SERVER_KEY, AsyncMock(spec=IEncryptionCache))

        if expected_error is None:
            # When:
            result = enc._decrypt_aes_key(encrypted_key_b64, shared_key)

            # Then:
            assert result == expected_result, test_case
        else:
            with pytest.raises(expected_error):
                enc._decrypt_aes_key(encrypted_key_b64, shared_key)

    @pytest.mark.parametrize(
        "test_case, encrypted_data_b64, aes_key, iv_b64, expected_result, expected_error, expected_error_msg",
        [
            pytest.param(
                "valid encrypted data is decrypted to the original plaintext",
                _ENCRYPTED_HELPER_DATA_B64,
                _HELPER_AES_KEY,
                _HELPER_DATA_IV_B64,
                _HELPER_PLAINTEXT,
                None,
                None,
                id="valid",
            ),
            pytest.param(
                "raises ValueError when the IV is not 12 bytes",
                _ENCRYPTED_HELPER_DATA_B64,
                _HELPER_AES_KEY,
                base64.b64encode(b"short").decode(),
                None,
                ValueError,
                "IV must be 12 bytes, got 5",
                id="invalid_iv_length",
            ),
            pytest.param(
                "corrupted ciphertext raises an exception",
                base64.b64encode(os.urandom(50)).decode(),
                _HELPER_AES_KEY,
                _HELPER_DATA_IV_B64,
                None,
                Exception,
                None,
                id="corrupted_data",
            ),
            pytest.param(
                "invalid base64 in encrypted_data raises an exception",
                "not-valid-base64!!!",
                _HELPER_AES_KEY,
                _HELPER_DATA_IV_B64,
                None,
                Exception,
                None,
                id="invalid_base64",
            ),
        ],
    )
    def test_decrypt_data(
        self,
        test_case: str,
        encrypted_data_b64: str,
        aes_key: bytes,
        iv_b64: str,
        expected_result: bytes | None,
        expected_error: type[Exception] | None,
        expected_error_msg: str | None,
    ):
        enc = Encryption(_SERVER_KEY, AsyncMock(spec=IEncryptionCache))

        if expected_error is None:
            # When:
            result = enc._decrypt_data(encrypted_data_b64, aes_key, iv_b64)

            # Then:
            assert result == expected_result, test_case
        else:
            match = re.escape(expected_error_msg) if expected_error_msg else None
            with pytest.raises(expected_error, match=match):
                enc._decrypt_data(encrypted_data_b64, aes_key, iv_b64)
