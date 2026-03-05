"""
Unit tests for routers/common.py shared dependencies and utilities.
"""

from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from routers.common import init_k8s_client, init_models_dict
from services.data_sanitizer import IDataSanitizer
from utils.models_cache import reset_models_cache_for_tests


class TestInitK8sClient:
    """Tests for init_k8s_client dependency."""

    @pytest.fixture
    def mock_data_sanitizer(self):
        """Create a mock DataSanitizer."""
        return Mock(spec=IDataSanitizer)

    @pytest.fixture
    def valid_headers(self):
        """Provide valid K8s authentication headers."""
        return {
            "x_cluster_url": "https://api.test-cluster.example.com",
            "x_cluster_certificate_authority_data": "LS0tLS1CRUdJTi1DRVJUSUZJQ0FURS0tLS0t",
            "x_k8s_authorization": "test-token-123",
        }

    def test_init_k8s_client_raises_422_on_validation_error(self, valid_headers, mock_data_sanitizer):
        """Test that init_k8s_client raises 422 when headers validation fails."""
        with patch("routers.common.K8sAuthHeaders") as mock_auth_class:
            mock_auth = Mock()
            mock_auth.validate_headers.side_effect = ValueError("Invalid authentication: no credentials provided")
            mock_auth_class.return_value = mock_auth

            with pytest.raises(HTTPException) as exc_info:
                init_k8s_client(
                    x_cluster_url=valid_headers["x_cluster_url"],
                    x_cluster_certificate_authority_data=valid_headers["x_cluster_certificate_authority_data"],
                    data_sanitizer=mock_data_sanitizer,
                    x_k8s_authorization=None,
                    x_client_certificate_data=None,
                    x_client_key_data=None,
                )

            assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
            assert "Invalid authentication" in str(exc_info.value.detail)


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
        reset_models_cache_for_tests()
        yield
        reset_models_cache_for_tests()

    def test_init_models_dict_caches_result(self, mock_config):
        """Test that init_models_dict caches models dict (singleton behavior)."""
        with patch("utils.models_cache.ModelFactory") as mock_factory_class:
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
        with patch("utils.models_cache.ModelFactory") as mock_factory_class:
            mock_factory = Mock()
            mock_factory.create_models.side_effect = Exception("Model initialization failed")
            mock_factory_class.return_value = mock_factory

            with pytest.raises(HTTPException) as exc_info:
                init_models_dict(mock_config)

            assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
