"""
Generic ECDH + AES-256-GCM decryption service.

Wire formats expected by :py:meth:`Encryption.decrypt`:

* ``encrypted_key``:  base64(nonce[12B] ‖ AES-256-key ciphertext ‖ GCM-tag[16B])
  — the random AES-256 session key wrapped with the ECDH-derived shared key.
* ``iv``:             base64(nonce[12B])
  — GCM nonce used to encrypt the payload.
* ``encrypted_data``: base64(payload ciphertext ‖ GCM-tag[16B])
  — the actual data encrypted with the AES-256 session key.
"""

import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import load_der_private_key

from utils.settings import TEST_CLIENT_PUBLIC_KEY_B64

_ECDH_CURVE = ec.SECP256R1()
_HKDF_INFO = b"ecdh-key-exchange"
_AES_GCM_NONCE_SIZE = 12


class Encryption:
    """
    Generic ECDH + AES-256-GCM decryption service.
    """

    def __init__(self, private_key_b64: str) -> None:
        """Load and validate the server EC private key.

        :param private_key_b64: Base64-encoded DER/PKCS8 EC private key.
        :raises TypeError: If the key is not an EC private key.
        :raises ValueError: If the key cannot be decoded or loaded.
        """
        raw = base64.b64decode(private_key_b64)
        key = load_der_private_key(raw, password=None)
        if not isinstance(key, EllipticCurvePrivateKey):
            raise TypeError("private_key_b64 is not an EC private key")
        self._private_key: EllipticCurvePrivateKey = key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decrypt(
        self,
        encrypted_key: str,
        iv: str,
        client_public_key_id: str,
        encrypted_data: str,
    ) -> bytes:
        """Decrypt an ECDH + AES-GCM encrypted payload.

        :param encrypted_key: base64(nonce[12B] ‖ wrapped-AES-key ‖ GCM-tag[16B])
        :param iv: base64-encoded 12-byte GCM nonce used to encrypt *encrypted_data*.
        :param client_public_key_id: Identifier used to resolve the client's
            ECDH public key (e.g. a session Id).
        :param encrypted_data: base64(payload ciphertext ‖ GCM-tag[16B])
        :returns: Decrypted data as a ``bytes``.
        """
        client_public_key_b64 = self._get_client_public_key(client_public_key_id)
        shared_key = self._derive_shared_key(client_public_key_b64)
        aes_key = self._decrypt_aes_key(encrypted_key, shared_key)
        return self._decrypt_data(encrypted_data, aes_key, iv)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client_public_key(self, client_public_key_id: str) -> str:
        """Resolve the client's ECDH public key (base64-encoded EC point).

        TODO: Replace with a session-store lookup keyed by *client_public_key_id*.
        """
        return str(TEST_CLIENT_PUBLIC_KEY_B64)

    def _derive_shared_key(self, client_public_key_b64: str) -> bytes:
        """Perform ECDH and derive a 256-bit symmetric key via HKDF-SHA256.

        The client public key must be the raw uncompressed EC point
        (65 bytes for P-256), base64-encoded.
        """
        client_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            _ECDH_CURVE,
            base64.b64decode(client_public_key_b64),
        )
        shared_secret = self._private_key.exchange(ec.ECDH(), client_public_key)
        return HKDF(
            algorithm=SHA256(),
            length=32,
            salt=None,
            info=_HKDF_INFO,
        ).derive(shared_secret)

    def _decrypt_aes_key(self, encrypted_key_b64: str, shared_key: bytes) -> bytes:
        """Decrypt the AES-256 session key using the ECDH-derived shared key.

        Wire format after base64 decode::

            nonce[12B] ‖ ciphertext ‖ GCM-tag[16B]
        """
        raw = base64.b64decode(encrypted_key_b64)
        nonce = raw[:_AES_GCM_NONCE_SIZE]
        ciphertext_with_tag = raw[_AES_GCM_NONCE_SIZE:]
        return AESGCM(shared_key).decrypt(nonce, ciphertext_with_tag, None)

    def _decrypt_data(
        self,
        encrypted_data_b64: str,
        aes_key: bytes,
        iv_b64: str,
    ) -> bytes:
        """Decrypt the payload using AES-256-GCM and return parsed JSON.

        Wire format of *encrypted_data_b64* after base64 decode::

            ciphertext ‖ GCM-tag[16B]
        """
        iv = base64.b64decode(iv_b64)
        if len(iv) != _AES_GCM_NONCE_SIZE:
            raise ValueError(f"IV must be {_AES_GCM_NONCE_SIZE} bytes, got {len(iv)}")
        ciphertext_with_tag = base64.b64decode(encrypted_data_b64)
        return AESGCM(aes_key).decrypt(iv, ciphertext_with_tag, None)
