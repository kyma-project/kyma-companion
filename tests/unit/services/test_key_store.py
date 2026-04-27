"""Unit tests for services/key_store.py."""

import base64
import re
import time

import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from services.key_store import (
    KeyStore,
    _load_private_key,
    _load_private_key_from_file,
)

_ECDH_CURVE = ec.SECP256R1()
_UNCOMPRESSED_EC_POINT_LENGTH = 65  # 04 || X(32) || Y(32)
_UNCOMPRESSED_EC_POINT_PREFIX = 0x04


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ec_key_pem_bytes(key: EllipticCurvePrivateKey) -> bytes:
    """Encode an EC private key as PEM/PKCS8 bytes."""
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())


def _ec_key_der_bytes(key: EllipticCurvePrivateKey) -> bytes:
    """Encode an EC private key as DER/PKCS8 bytes."""
    return key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())


def _ec_public_key_b64(key: EllipticCurvePrivateKey) -> str:
    """Encode the uncompressed public point of an EC key as base64."""
    return base64.b64encode(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)).decode()


# ---------------------------------------------------------------------------
# Module-level test vectors
# ---------------------------------------------------------------------------

_SERVER_KEY = ec.generate_private_key(_ECDH_CURVE)
_SERVER_KEY_PEM = _ec_key_pem_bytes(_SERVER_KEY)
_SERVER_KEY_DER = _ec_key_der_bytes(_SERVER_KEY)
_SERVER_PUBLIC_KEY_B64 = _ec_public_key_b64(_SERVER_KEY)

_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_RSA_KEY_DER = _RSA_KEY.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())


# ---------------------------------------------------------------------------
# Tests — _load_private_key (module-level function)
# ---------------------------------------------------------------------------


class TestLoadPrivateKey:
    @pytest.mark.parametrize(
        "test_case, data, expected_error, expected_error_msg",
        [
            pytest.param(
                "PEM-encoded EC key is loaded successfully",
                _SERVER_KEY_PEM,
                None,
                None,
                id="pem_ec_key",
            ),
            pytest.param(
                "DER-encoded EC key is loaded successfully",
                _SERVER_KEY_DER,
                None,
                None,
                id="der_ec_key",
            ),
            pytest.param(
                "RSA DER key raises TypeError",
                _RSA_KEY_DER,
                TypeError,
                "Key is not an EC private key",
                id="rsa_key",
            ),
            pytest.param(
                "garbage bytes raise an exception",
                b"garbage data",
                Exception,
                None,
                id="garbage_data",
            ),
            pytest.param(
                "empty bytes raise an exception",
                b"",
                Exception,
                None,
                id="empty_data",
            ),
        ],
    )
    def test_load_private_key(
        self,
        test_case: str,
        data: bytes,
        expected_error: type[Exception] | None,
        expected_error_msg: str | None,
    ):
        if expected_error is None:
            # When:
            key = _load_private_key(data)

            # Then:
            assert isinstance(key, EllipticCurvePrivateKey), test_case
        else:
            match = re.escape(expected_error_msg) if expected_error_msg else None
            with pytest.raises(expected_error, match=match):
                _load_private_key(data)


# ---------------------------------------------------------------------------
# Tests — _load_private_key_from_file (module-level function)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_case, file_content, expected_error, expected_error_msg",
    [
        pytest.param(
            "PEM file is loaded successfully",
            _SERVER_KEY_PEM,
            None,
            None,
            id="pem_file",
        ),
        pytest.param(
            "DER file is loaded successfully",
            _SERVER_KEY_DER,
            None,
            None,
            id="der_file",
        ),
        pytest.param(
            "missing file raises FileNotFoundError",
            None,
            FileNotFoundError,
            None,
            id="missing_file",
        ),
        pytest.param(
            "garbage file raises an exception",
            b"not a valid key",
            Exception,
            None,
            id="garbage_file",
        ),
    ],
)
def test_load_private_key_from_file(
    tmp_path,
    test_case: str,
    file_content: bytes | None,
    expected_error: type[Exception] | None,
    expected_error_msg: str | None,
):
    key_file = tmp_path / "tls.key"
    if file_content is not None:
        key_file.write_bytes(file_content)

    if expected_error is None:
        # When:
        key = _load_private_key_from_file(key_file)

        # Then:
        assert isinstance(key, EllipticCurvePrivateKey), test_case
    else:
        match = re.escape(expected_error_msg) if expected_error_msg else None
        with pytest.raises(expected_error, match=match):
            _load_private_key_from_file(key_file)


# ---------------------------------------------------------------------------
# Tests — KeyStore class
# ---------------------------------------------------------------------------


class TestKeyStore:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the KeyStore singleton before and after each test."""
        KeyStore._reset_for_tests()
        yield
        KeyStore._reset_for_tests()

    @pytest.fixture()
    def key_file(self, tmp_path, monkeypatch):
        """Create a temp key file and point ENCRYPTION_PRIVATE_KEY_PATH at it."""
        path = tmp_path / "tls.key"
        monkeypatch.setattr("services.key_store.ENCRYPTION_PRIVATE_KEY_PATH", str(path))
        return path

    # -- __init__ / _load_key -----------------------------------------------

    @pytest.mark.parametrize(
        "test_case, file_content, expected_error, expected_error_msg",
        [
            pytest.param(
                "PEM key file is loaded successfully",
                _SERVER_KEY_PEM,
                None,
                None,
                id="pem_file",
            ),
            pytest.param(
                "DER key file is loaded successfully",
                _SERVER_KEY_DER,
                None,
                None,
                id="der_file",
            ),
            pytest.param(
                "missing file raises FileNotFoundError",
                None,
                FileNotFoundError,
                None,
                id="missing_file",
            ),
            pytest.param(
                "garbage file raises ValueError",
                b"not a valid key",
                ValueError,
                None,
                id="garbage_file",
            ),
            pytest.param(
                "RSA key file raises TypeError",
                _RSA_KEY_DER,
                TypeError,
                "Key is not an EC private key",
                id="rsa_key_file",
            ),
        ],
    )
    def test_init(
        self,
        key_file,
        test_case: str,
        file_content: bytes | None,
        expected_error: type[Exception] | None,
        expected_error_msg: str | None,
    ):
        if file_content is not None:
            key_file.write_bytes(file_content)

        if expected_error is None:
            store = KeyStore()
            assert isinstance(store._key, EllipticCurvePrivateKey), test_case
        else:
            match = re.escape(expected_error_msg) if expected_error_msg else None
            with pytest.raises(expected_error, match=match):
                KeyStore()

    # -- singleton behaviour ------------------------------------------------

    def test_singleton_returns_same_instance(self, key_file):
        """Successive KeyStore() calls return the same singleton instance."""
        key_file.write_bytes(_SERVER_KEY_PEM)

        store1 = KeyStore()
        store2 = KeyStore()

        assert store1 is store2

    def test_reset_for_tests_clears_singleton(self, key_file):
        """_reset_for_tests allows a fresh instance to be created."""
        key_file.write_bytes(_SERVER_KEY_PEM)

        store1 = KeyStore()
        KeyStore._reset_for_tests()

        # Generate a different key so we can distinguish the instances.
        other_key = ec.generate_private_key(_ECDH_CURVE)
        key_file.write_bytes(_ec_key_pem_bytes(other_key))

        store2 = KeyStore()

        assert store1 is not store2

    # -- get_private_key ----------------------------------------------------

    @pytest.mark.parametrize(
        "test_case, file_content, expected_error, expected_error_msg",
        [
            pytest.param(
                "returns the EC private key when the file is valid PEM",
                _SERVER_KEY_PEM,
                None,
                None,
                id="valid_pem",
            ),
            pytest.param(
                "returns the EC private key when the file is valid DER",
                _SERVER_KEY_DER,
                None,
                None,
                id="valid_der",
            ),
        ],
    )
    def test_get_private_key(
        self,
        key_file,
        test_case: str,
        file_content: bytes,
        expected_error: type[Exception] | None,
        expected_error_msg: str | None,
    ):
        key_file.write_bytes(file_content)
        store = KeyStore()

        if expected_error is None:
            # When:
            result = store.get_private_key()

            # Then:
            assert isinstance(result, EllipticCurvePrivateKey), test_case
        else:
            match = re.escape(expected_error_msg) if expected_error_msg else None
            with pytest.raises(expected_error, match=match):
                store.get_private_key()

    # -- get_public_key -----------------------------------------------------

    def test_get_public_key(self, key_file):
        """get_public_key returns an EllipticCurvePublicKey derived from the private key."""
        key_file.write_bytes(_SERVER_KEY_PEM)
        store = KeyStore()

        # When:
        result = store.get_public_key()

        # Then:
        assert isinstance(result, EllipticCurvePublicKey)

    # -- get_public_key_str -------------------------------------------------

    def test_get_public_key_str(self, key_file):
        """get_public_key_str returns a base64-encoded uncompressed EC point."""
        key_file.write_bytes(_SERVER_KEY_PEM)
        store = KeyStore()

        # When:
        result = store.get_public_key_str()

        # Then:
        assert result == _SERVER_PUBLIC_KEY_B64
        raw = base64.b64decode(result)
        # Uncompressed EC point for P-256: 04 || X(32) || Y(32) = 65 bytes.
        assert len(raw) == _UNCOMPRESSED_EC_POINT_LENGTH
        assert raw[0] == _UNCOMPRESSED_EC_POINT_PREFIX

    # -- staleness / reload -------------------------------------------------

    def test_reload_if_stale_reloads_after_interval(self, key_file, monkeypatch):
        """The key is reloaded from disk when the cached copy exceeds the reload interval."""
        key_file.write_bytes(_SERVER_KEY_PEM)
        store = KeyStore()

        original_key = store.get_private_key()

        # Write a new key to the same file.
        new_key = ec.generate_private_key(_ECDH_CURVE)
        key_file.write_bytes(_ec_key_pem_bytes(new_key))

        # Simulate time passing beyond the reload interval.
        monkeypatch.setattr(time, "monotonic", lambda: store._loaded_at + 30 * 60 + 1)

        # When:
        reloaded_key = store.get_private_key()

        # Then: the key should have changed (different serialization).
        original_bytes = original_key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        reloaded_bytes = reloaded_key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        assert original_bytes != reloaded_bytes

    def test_no_reload_when_not_stale(self, key_file, monkeypatch):
        """The key is NOT reloaded when the cached copy is still fresh."""
        key_file.write_bytes(_SERVER_KEY_PEM)
        store = KeyStore()

        original_key = store.get_private_key()

        # Write a different key to disk.
        new_key = ec.generate_private_key(_ECDH_CURVE)
        key_file.write_bytes(_ec_key_pem_bytes(new_key))

        # Simulate time NOT exceeding the reload interval.
        monkeypatch.setattr(time, "monotonic", lambda: store._loaded_at + 30 * 60 - 1)

        # When:
        cached_key = store.get_private_key()

        # Then: should still return the original cached key.
        original_bytes = original_key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        cached_bytes = cached_key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        assert original_bytes == cached_bytes

    def test_reload_failure_preserves_cached_key(self, key_file, monkeypatch):
        """When reload fails, the last-known-good key is preserved and returned."""
        key_file.write_bytes(_SERVER_KEY_PEM)
        store = KeyStore()

        original_key = store.get_private_key()

        # Remove the key file to simulate a transient failure during secret rotation.
        key_file.unlink()

        # Simulate time passing beyond the reload interval.
        monkeypatch.setattr(time, "monotonic", lambda: store._loaded_at + 30 * 60 + 1)

        # When: get_private_key should NOT raise — it should return the cached key.
        result = store.get_private_key()

        # Then: the original key is still served.
        original_bytes = original_key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        result_bytes = result.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        assert original_bytes == result_bytes

    def test_reload_failure_bumps_loaded_at(self, key_file, monkeypatch):
        """After a failed reload, _loaded_at is updated to avoid retrying on every call."""
        key_file.write_bytes(_SERVER_KEY_PEM)
        store = KeyStore()

        # Remove the file and trigger a stale reload.
        key_file.unlink()
        stale_time = store._loaded_at + 30 * 60 + 1
        monkeypatch.setattr(time, "monotonic", lambda: stale_time)
        store.get_private_key()

        # _loaded_at should have been bumped to stale_time.
        assert store._loaded_at == stale_time

    # -- is_healthy ---------------------------------------------------------

    @pytest.mark.parametrize(
        "test_case, setup_fn, expected_result",
        [
            pytest.param(
                "returns True when a valid key is loaded",
                lambda store, key_file, monkeypatch: None,  # No special setup needed
                True,
                id="valid_key",
            ),
            pytest.param(
                "returns False when the key is None",
                lambda store, key_file, monkeypatch: setattr(store, "_key", None),
                False,
                id="key_none",
            ),
            pytest.param(
                "returns False when get_public_key_str raises an exception",
                lambda store, key_file, monkeypatch: monkeypatch.setattr(
                    store, "get_public_key_str", lambda: (_ for _ in ()).throw(RuntimeError("Key unavailable"))
                ),
                False,
                id="exception_raised",
            ),
        ],
    )
    def test_is_healthy(self, key_file, monkeypatch, test_case, setup_fn, expected_result):
        """is_healthy returns True for a valid key, False otherwise."""
        key_file.write_bytes(_SERVER_KEY_PEM)
        store = KeyStore()

        # Apply test-specific setup
        setup_fn(store, key_file, monkeypatch)

        # When:
        result = store.is_healthy()

        # Then:
        assert result is expected_result, test_case

    # -- fallback to ENCRYPTION_PRIVATE_KEY_B64 -----------------------------

    def test_load_key_falls_back_to_b64_config(self, monkeypatch):
        """When path is empty, _load_key reads from ENCRYPTION_PRIVATE_KEY_B64."""
        b64_value = base64.b64encode(_SERVER_KEY_DER).decode()
        monkeypatch.setattr("services.key_store.ENCRYPTION_PRIVATE_KEY_B64", b64_value)
        monkeypatch.setattr("services.key_store.ENCRYPTION_PRIVATE_KEY_PATH", "")

        store = KeyStore()

        assert isinstance(store.get_private_key(), EllipticCurvePrivateKey)
