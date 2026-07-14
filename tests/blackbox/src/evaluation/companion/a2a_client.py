"""A2A (Agent-to-Agent) client for the Kyma agent endpoint.

Sends JSON-RPC ``message/send`` requests to ``POST /api/agent/kyma/chat``.
Encrypted K8s credentials are embedded inside the message metadata, exactly
as the server's KymaAgentExecutor expects them.

Multi-turn conversations are supported: the server echoes back a
``context_id`` in the response message; pass it as ``context_id`` on
subsequent calls to continue the same conversation.
"""

import base64
import json
import logging
import os
import time
import uuid
from http import HTTPStatus

import requests
from common.config import Config
from common.metrics import Metrics
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA384
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

logger = logging.getLogger(__name__)

_ECDH_CURVE = ec.SECP521R1()
_HKDF_INFO = b"ecdh-key-exchange"
_AES_GCM_NONCE_SIZE = 12


def _encrypt_cluster_payload(
    companion_public_key_b64: str,
    client_private_key: ec.EllipticCurvePrivateKey,
    aes_key: bytes,
    key_nonce: bytes,
    iv: bytes,
    plaintext: bytes,
) -> tuple[str, str, str]:
    """Encrypt cluster credentials using ECDH + AES-256-GCM.

    Returns (x_encrypted_key, x_client_iv, x_target_cluster_encrypted).
    """
    companion_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
        _ECDH_CURVE, base64.b64decode(companion_public_key_b64)
    )
    shared_secret = client_private_key.exchange(ec.ECDH(), companion_public_key)
    shared_key = HKDF(
        algorithm=SHA384(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    ).derive(shared_secret)

    encrypted_aes_key = AESGCM(shared_key).encrypt(key_nonce, aes_key, None)
    x_encrypted_key = base64.b64encode(key_nonce + encrypted_aes_key).decode()

    encrypted_data = AESGCM(aes_key).encrypt(iv, plaintext, None)
    x_client_iv = base64.b64encode(iv).decode()
    x_target_cluster_encrypted = base64.b64encode(encrypted_data).decode()

    return x_encrypted_key, x_client_iv, x_target_cluster_encrypted


class A2AEncryptionSession:
    """Holds the ECDH session state shared across multiple requests.

    Create once per test run by calling ``A2AEncryptionSession.create()``.
    """

    def __init__(
        self,
        client_private_key: ec.EllipticCurvePrivateKey,
        session_id: str,
        companion_public_key_b64: str,
        aes_key: bytes,
        plaintext: bytes,
    ) -> None:
        self._client_private_key = client_private_key
        self.session_id = session_id
        self._companion_public_key_b64 = companion_public_key_b64
        self._aes_key = aes_key
        self._plaintext = plaintext

    @classmethod
    def create(cls, config: Config) -> "A2AEncryptionSession":
        """Perform the ECDH key exchange and return a ready-to-use session."""
        client_private_key = ec.generate_private_key(_ECDH_CURVE)
        client_public_key_b64 = base64.b64encode(
            client_private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        ).decode()

        response = requests.post(
            f"{config.companion_api_url}/api/public-key",
            json={"public_key": client_public_key_b64},
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        if response.status_code != HTTPStatus.OK:
            raise RuntimeError(f"Failed to register client public key: {response.text}")

        body = response.json()

        plaintext = json.dumps(
            {
                "x-cluster-url": config.test_cluster_url,
                "x-cluster-certificate-authority-data": config.test_cluster_ca_data,
                "x-k8s-authorization": config.test_cluster_auth_token,
            }
        ).encode()

        return cls(
            client_private_key=client_private_key,
            session_id=body["session_id"],
            companion_public_key_b64=body["companion_public_key"],
            aes_key=os.urandom(32),
            plaintext=plaintext,
        )

    def build_encrypted_metadata(
        self,
        namespace: str = "",
        resource_type: str = "",
        resource_name: str = "",
        group_version: str = "",
    ) -> dict[str, str]:
        """Return message metadata dict with fresh nonces for one request."""
        key_nonce = os.urandom(_AES_GCM_NONCE_SIZE)
        iv = os.urandom(_AES_GCM_NONCE_SIZE)

        x_encrypted_key, x_client_iv, x_target_cluster_encrypted = _encrypt_cluster_payload(
            self._companion_public_key_b64,
            self._client_private_key,
            self._aes_key,
            key_nonce,
            iv,
            self._plaintext,
        )

        return {
            "x-encrypted-key": x_encrypted_key,
            "x-client-iv": x_client_iv,
            "x-session-id": self.session_id,
            "x-target-cluster-encrypted": x_target_cluster_encrypted,
            "namespace": namespace,
            "resourceType": resource_type,
            "resourceName": resource_name,
            "groupVersion": group_version,
        }


class A2AClient:
    """HTTP client for the Kyma A2A agent endpoint.

    Wraps the JSON-RPC ``message/send`` protocol and handles multi-turn
    conversation state via ``context_id``.
    """

    def __init__(self, config: Config, encryption_session: A2AEncryptionSession) -> None:
        self.config = config
        self._encryption_session = encryption_session
        self._base_url = f"{config.companion_api_url}/api/agent/kyma/chat"

    def send_message(
        self,
        query: str,
        resource_kind: str = "",
        resource_name: str = "",
        resource_api_version: str = "",
        namespace: str = "",
        context_id: str | None = None,
    ) -> tuple[str, str]:
        """Send a message to the A2A endpoint and return (answer, context_id).

        Args:
            query: The user's question.
            resource_kind: K8s/Kyma resource kind the user is viewing (UI context).
            resource_name: Name of the resource the user is viewing.
            resource_api_version: API version of the resource.
            namespace: Namespace of the resource.
            context_id: Conversation context ID from a previous response.
                        Pass None for the first message in a new conversation.

        Returns:
            A tuple of (answer_text, context_id).  The returned context_id
            must be passed back in subsequent calls to continue the conversation.
        """
        message_id = str(uuid.uuid4())
        metadata = self._encryption_session.build_encrypted_metadata(
            namespace=namespace,
            resource_type=resource_kind,
            resource_name=resource_name,
            group_version=resource_api_version,
        )

        message: dict = {
            "role": "user",
            "parts": [{"text": query, "kind": "text"}],
            "messageId": message_id,
            "metadata": metadata,
            "kind": "message",
        }
        if context_id:
            message["contextId"] = context_id

        payload = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "message/send",
            "params": {"message": message},
        }

        start_time = time.time()
        response = requests.post(
            self._base_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.config.streaming_response_timeout,
        )

        Metrics.get_instance().record_conversation_response_time(time.time() - start_time)

        if response.status_code != HTTPStatus.OK:
            raise ValueError(f"A2A request failed (status {response.status_code}): {response.text}")

        body = response.json()

        # Handle JSON-RPC error object
        if "error" in body:
            raise ValueError(f"A2A JSON-RPC error: {body['error']}")

        result = body.get("result", {})

        # The result may be a Task (with a status.message) or a plain Message.
        answer = self._extract_answer(result)
        returned_context_id = self._extract_context_id(result) or context_id or message_id

        return answer, returned_context_id

    @staticmethod
    def _extract_answer(result: dict) -> str:
        """Pull the text answer out of a Task or Message result."""
        # Task result: result.status.message.parts[].text
        status = result.get("status", {})
        message = status.get("message") or result  # fall back to the result as a message
        parts = message.get("parts", [])
        for part in parts:
            text = part.get("text", "")
            if text:
                return str(text)
        raise ValueError(f"No text content found in A2A result: {result}")

    @staticmethod
    def _extract_context_id(result: dict) -> str | None:
        """Extract context_id from a Task or Message result."""
        # Task: result.contextId
        # Message: result.contextId (if the result itself is a message)
        context_id = result.get("contextId")
        if context_id:
            return str(context_id)

        status = result.get("status", {})
        message = status.get("message", {})
        context_id = message.get("contextId")
        return str(context_id) if context_id is not None else None
