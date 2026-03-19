"""
Unit tests for routers/common.py shared dependencies and utilities.
"""

import json
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from routers.common import get_k8s_auth_headers_from_encrypted_payload, init_k8s_client, init_models_dict
from services.data_sanitizer import IDataSanitizer
from services.encryption_cache import IEncryptionCache
from services.k8s import K8sAuthHeaders

_PRIVATE_KEY_B64 = "fake-private-key-b64"
_VALID_PAYLOAD = {
    "x-cluster-url": "https://api.test-cluster.example.com",
    "x-cluster-certificate-authority-data": "dGVzdC1jYS1kYXRh",
    "x-k8s-authorization": "Bearer test-token",
}
_VALID_PAYLOAD_BYTES = json.dumps(_VALID_PAYLOAD).encode()


class TestInitK8sClient:
    """Tests for init_k8s_client dependency."""

    @pytest.fixture
    def mock_data_sanitizer(self):
        return Mock(spec=IDataSanitizer)

    @pytest.fixture
    def mock_encryption_cache(self):
        return AsyncMock(spec=IEncryptionCache)

    @pytest.fixture
    def plain_headers(self):
        return {
            "x_cluster_url": "https://api.test-cluster.example.com",
            "x_cluster_certificate_authority_data": "LS0tLS1CRUdJTi1DRVJUSUZJQ0FURS0tLS0t",
            "x_k8s_authorization": "test-token-123",
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "description, x_target_cluster_encrypted, validate_side_effect, encrypted_path_side_effect, expected_status, expected_detail_fragment",
        [
            pytest.param(
                "returns a K8sClient when plain headers are valid",
                None,
                None,
                None,
                None,
                None,
                id="plain_headers_success",
            ),
            pytest.param(
                "raises 422 when plain header validation fails",
                None,
                ValueError("Invalid authentication: no credentials provided"),
                None,
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Invalid authentication",
                id="plain_headers_validation_error",
            ),
            pytest.param(
                "uses encrypted headers when x_target_cluster_encrypted is provided",
                "enc-data",
                None,
                None,
                None,
                None,
                id="encrypted_path_success",
            ),
            pytest.param(
                "propagates HTTPException raised by the encrypted path helper unchanged",
                "enc-data",
                None,
                HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="bad encrypted header"),
                HTTPStatus.BAD_REQUEST,
                "bad encrypted header",
                id="encrypted_path_http_exception",
            ),
        ],
    )
    async def test_init_k8s_client(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_data_sanitizer: Mock,
        mock_encryption_cache: AsyncMock,
        plain_headers: dict,
        description: str,
        x_target_cluster_encrypted: str | None,
        validate_side_effect: Exception | None,
        encrypted_path_side_effect: Exception | None,
        expected_status: HTTPStatus | None,
        expected_detail_fragment: str | None,
    ):
        # Given:
        mock_auth = Mock()
        mock_auth.validate_headers.side_effect = validate_side_effect

        if x_target_cluster_encrypted:
            monkeypatch.setattr(
                "routers.common.get_k8s_auth_headers_from_encrypted_payload",
                AsyncMock(
                    side_effect=encrypted_path_side_effect,
                    return_value=mock_auth if encrypted_path_side_effect is None else None,
                ),
            )

        mock_k8s_client = Mock()

        with (
            patch("routers.common.K8sAuthHeaders", return_value=mock_auth),
            patch("routers.common.K8sClient", return_value=mock_k8s_client),
        ):
            # When / Then:
            if expected_status is not None:
                with pytest.raises(HTTPException) as exc_info:
                    await init_k8s_client(
                        data_sanitizer=mock_data_sanitizer,
                        encryption_cache=mock_encryption_cache,
                        x_cluster_url=plain_headers["x_cluster_url"],
                        x_cluster_certificate_authority_data=plain_headers["x_cluster_certificate_authority_data"],
                        x_k8s_authorization=plain_headers["x_k8s_authorization"],
                        x_target_cluster_encrypted=x_target_cluster_encrypted,
                    )
                assert exc_info.value.status_code == expected_status, description
                if expected_detail_fragment:
                    assert expected_detail_fragment in exc_info.value.detail, description
            else:
                result = await init_k8s_client(
                    data_sanitizer=mock_data_sanitizer,
                    encryption_cache=mock_encryption_cache,
                    x_cluster_url=plain_headers["x_cluster_url"],
                    x_cluster_certificate_authority_data=plain_headers["x_cluster_certificate_authority_data"],
                    x_k8s_authorization=plain_headers["x_k8s_authorization"],
                    x_target_cluster_encrypted=x_target_cluster_encrypted,
                )
                assert result is mock_k8s_client, description


class TestInitModelsDict:
    """Tests for init_models_dict dependency (caching behavior)."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock Config with models configuration."""
        config = Mock()
        config.models = [
            {"name": "gpt-4", "type": "azure_openai"},
        ]
        return config

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset the models cache before each test."""
        from routers.common import _ModelsCache

        _ModelsCache._instance = None
        yield
        _ModelsCache._instance = None

    def test_init_models_dict_caches_result(self, mock_config):
        """Test that init_models_dict caches models dict (singleton behavior)."""
        with patch("routers.common.ModelFactory") as mock_factory_class:
            mock_factory = Mock()
            mock_models = {"gpt-4": Mock()}
            mock_factory.create_models.return_value = mock_models
            mock_factory_class.return_value = mock_factory

            # First call
            result1 = init_models_dict(mock_config)
            # Second call
            result2 = init_models_dict(mock_config)

            # Should return same instance (cached)
            assert result1 is result2
            # Factory should only be called once due to caching
            assert mock_factory_class.call_count == 1

    def test_init_models_dict_raises_http_exception_on_error(self, mock_config):
        """Test that init_models_dict raises HTTPException when model creation fails."""
        with patch("routers.common.ModelFactory") as mock_factory_class:
            mock_factory = Mock()
            mock_factory.create_models.side_effect = Exception("Model initialization failed")
            mock_factory_class.return_value = mock_factory

            with pytest.raises(HTTPException) as exc_info:
                init_models_dict(mock_config)

            assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description, private_key_b64, x_encrypted_key, x_client_iv, x_target_cluster_encrypted, decrypt_effect, decrypt_return, expected_status, expected_detail_fragment, expected_fields",
    [
        pytest.param(
            "valid encrypted payload is decrypted and parsed into K8sAuthHeaders",
            _PRIVATE_KEY_B64,
            "enc-key",
            "iv",
            "enc-data",
            None,
            _VALID_PAYLOAD_BYTES,
            None,
            None,
            {
                "x_cluster_url": "https://api.test-cluster.example.com",
                "x_cluster_certificate_authority_data": "dGVzdC1jYS1kYXRh",
                "x_k8s_authorization": "Bearer test-token",
            },
            id="success",
        ),
        pytest.param(
            "raises 500 when the server private key is not configured",
            "",
            "enc-key",
            "iv",
            "enc-data",
            None,
            None,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Encrypted Auth Headers are not enabled in companion",
            None,
            id="private_key_not_configured",
        ),
        pytest.param(
            "raises 400 when x_encrypted_key header is missing",
            _PRIVATE_KEY_B64,
            "",
            "iv",
            "enc-data",
            None,
            None,
            HTTPStatus.BAD_REQUEST,
            "Missing required encrypted headers",
            None,
            id="missing_encrypted_key",
        ),
        pytest.param(
            "raises 400 when x_client_iv header is missing",
            _PRIVATE_KEY_B64,
            "enc-key",
            "",
            "enc-data",
            None,
            None,
            HTTPStatus.BAD_REQUEST,
            "Missing required encrypted headers",
            None,
            id="missing_client_iv",
        ),
        pytest.param(
            "raises 400 when x_target_cluster_encrypted header is missing",
            _PRIVATE_KEY_B64,
            "enc-key",
            "iv",
            "",
            None,
            None,
            HTTPStatus.BAD_REQUEST,
            "Missing required encrypted headers",
            None,
            id="missing_target_cluster_encrypted",
        ),
        pytest.param(
            "raises 400 when decryption raises a ValueError",
            _PRIVATE_KEY_B64,
            "enc-key",
            "iv",
            "enc-data",
            ValueError("Client public key not found: session-123"),
            None,
            HTTPStatus.BAD_REQUEST,
            "Client public key not found: session-123",
            None,
            id="decrypt_raises_value_error",
        ),
        pytest.param(
            "raises 422 when decryption raises a generic exception",
            _PRIVATE_KEY_B64,
            "enc-key",
            "iv",
            "enc-data",
            Exception("unexpected failure"),
            None,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Failed to decrypt cluster authentication headers",
            None,
            id="decrypt_raises_exception",
        ),
        pytest.param(
            "re-raises HTTPException from decryption unchanged",
            _PRIVATE_KEY_B64,
            "enc-key",
            "iv",
            "enc-data",
            HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE, detail="upstream error"),
            None,
            HTTPStatus.SERVICE_UNAVAILABLE,
            "upstream error",
            None,
            id="decrypt_raises_http_exception",
        ),
    ],
)
async def test_get_k8s_auth_headers_from_encrypted_payload(
    monkeypatch: pytest.MonkeyPatch,
    description: str,
    private_key_b64: str,
    x_encrypted_key: str,
    x_client_iv: str,
    x_target_cluster_encrypted: str,
    decrypt_effect: Exception | None,
    decrypt_return: bytes | None,
    expected_status: HTTPStatus | None,
    expected_detail_fragment: str | None,
    expected_fields: dict | None,
):
    # Given:
    monkeypatch.setattr("routers.common.ENCRYPTION_PRIVATE_KEY_B64", private_key_b64)

    mock_encryption_instance = Mock()
    mock_encryption_instance.decrypt = AsyncMock(side_effect=decrypt_effect, return_value=decrypt_return)
    monkeypatch.setattr("routers.common.Encryption", Mock(return_value=mock_encryption_instance))

    mock_cache = AsyncMock(spec=IEncryptionCache)

    # When / Then:
    if expected_status is not None:
        with pytest.raises(HTTPException) as exc_info:
            await get_k8s_auth_headers_from_encrypted_payload(
                x_encrypted_key,
                x_client_iv,
                "session-123",
                x_target_cluster_encrypted,
                mock_cache,
            )
        assert exc_info.value.status_code == expected_status, description
        if expected_detail_fragment:
            assert expected_detail_fragment in exc_info.value.detail, description
    else:
        result = await get_k8s_auth_headers_from_encrypted_payload(
            x_encrypted_key,
            x_client_iv,
            "session-123",
            x_target_cluster_encrypted,
            mock_cache,
        )
        assert isinstance(result, K8sAuthHeaders), description
        for field, value in (expected_fields or {}).items():
            assert getattr(result, field) == value, f"{description}: field {field}"
