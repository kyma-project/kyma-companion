"""
Singleton key store that loads an EC private key from a Kubernetes-mounted
secret file and transparently reloads it when the cached copy is stale.
"""

import base64
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_der_private_key,
    load_pem_private_key,
)

from utils.logging import get_logger
from utils.settings import ENCRYPTION_PRIVATE_KEY_B64, ENCRYPTION_PRIVATE_KEY_PATH
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)

_RELOAD_INTERVAL_SECONDS = 30 * 60  # 30 minutes


def _load_private_key(data: bytes) -> EllipticCurvePrivateKey:
    """Decode key data and return a validated EC private key.

    Supports both PEM and raw DER formats (after base64 decoding).

    :param data: Raw private key bytes in PEM or DER format.
    :raises TypeError: If the key is not an EC private key.
    :raises ValueError: If the data cannot be decoded or parsed as a private key.
    """

    # Try PEM first (has header line), fall back to DER.
    try:
        key = load_pem_private_key(data, password=None)
    except (ValueError, TypeError):
        key = load_der_private_key(data, password=None)

    if not isinstance(key, EllipticCurvePrivateKey):
        raise TypeError("Key is not an EC private key")
    return key


def _load_private_key_from_file(path: Path) -> EllipticCurvePrivateKey:
    """Read the key file and return a validated EC private key.

    Supports both PEM and raw DER formats.

    :raises FileNotFoundError: If *path* does not exist.
    :raises TypeError: If the key is not an EC private key.
    :raises ValueError: If the file cannot be parsed as a private key.
    """

    return _load_private_key(path.read_bytes())


class KeyStore(metaclass=SingletonMeta):
    """Singleton store for the ECDH key pair loaded from disk.

    The key file path is taken from the ``ENCRYPTION_PRIVATE_KEY_PATH``
    setting.  On every call to :py:meth:`get_private_key` or
    :py:meth:`get_public_key` the store checks whether the cached key is
    older than 30 minutes and reloads the file automatically — no restart
    required when Kubernetes rotates the secret.

    Usage::

        store = KeyStore()
        private = store.get_private_key()
        public  = store.get_public_key()
    """

    def __init__(self) -> None:
        self._path = str(ENCRYPTION_PRIVATE_KEY_PATH)
        self._key: EllipticCurvePrivateKey | None = None
        self._loaded_at: float = 0.0
        self._load_key()

    # ---- public API -------------------------------------------------------

    def get_private_key(self) -> EllipticCurvePrivateKey:
        """Return the EC private key, reloading from disk if stale.

        :raises RuntimeError: If the key cannot be loaded.
        """
        self._reload_if_stale()
        if self._key is None:
            raise RuntimeError(f"EC private key is not available (path={self._path})")
        return self._key

    def get_public_key(self) -> EllipticCurvePublicKey:
        """Return the EC public key derived from the private key, reloading from disk if stale.

        :raises RuntimeError: If the key cannot be loaded.
        """
        return self.get_private_key().public_key()

    def get_public_key_str(self) -> str:
        """Return the EC public key derived from the private key as a string, reloading from disk if stale.

        :raises RuntimeError: If the key cannot be loaded.
        """
        # Extract the raw uncompressed EC point (65 bytes: 04 || X || Y)
        raw_point = self.get_public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)

        # return the Base64-encoded raw point as a string
        return base64.b64encode(raw_point).decode("ascii")

    def is_healthy(self) -> bool:
        """Return True if the key store is healthy (i.e. has a valid key), False otherwise.

        This is used in the health probe to determine if the key store is operational.
        If the key cannot be loaded or parsed, this will return False, but it will not raise an exception.
        The health probe will log any exceptions encountered when trying to load the key.

        :return: bool
        """
        try:
            self.get_public_key_str()
            return True
        except Exception:
            return False

    # ---- internals --------------------------------------------------------

    def _reload_if_stale(self) -> None:
        """Reload the key file if the cached copy is older than the reload interval.

        If the reload fails (e.g. the file is temporarily missing during a
        secret rotation), the last-known-good key is preserved and a warning
        is logged.  ``_loaded_at`` is updated so we don't hammer the
        filesystem on every subsequent call.
        """
        if time.monotonic() - self._loaded_at >= _RELOAD_INTERVAL_SECONDS:
            logger.info("Cached key is stale (>%ds), reloading %s", _RELOAD_INTERVAL_SECONDS, self._path)
            try:
                self._load_key()
            except Exception:
                logger.warning(
                    "Failed to reload private key from %s — keeping previously cached key.",
                    self._path,
                    exc_info=True,
                )
                # Bump the timestamp so we don't retry on every single call.
                self._loaded_at = time.monotonic()

    def _load_key(self) -> None:
        """Load (or reload) the private key.

        Reads from the file at ``ENCRYPTION_PRIVATE_KEY_PATH`` when set,
        otherwise falls back to the ``ENCRYPTION_PRIVATE_KEY_B64`` config value.

        :raises FileNotFoundError: If the key file path is set but does not exist.
        :raises TypeError: If the key is not an EC private key.
        :raises ValueError: If the key data cannot be decoded or parsed.
        """
        if not self._path:
            logger.warning(
                "ENCRYPTION_PRIVATE_KEY_PATH is not set, reading from configuration value ENCRYPTION_PRIVATE_KEY_B64"
            )
            self._key = _load_private_key(base64.b64decode(str(ENCRYPTION_PRIVATE_KEY_B64)))
            self._loaded_at = time.monotonic()
            return
        self._key = _load_private_key_from_file(Path(self._path))
        self._loaded_at = time.monotonic()
        logger.info("EC private key loaded from %s", self._path)

    # ---- test helpers -----------------------------------------------------

    @classmethod
    def _reset_for_tests(cls) -> None:
        """Remove the singleton instance so it can be re-created in tests."""
        SingletonMeta.reset_instance(cls)
