"""Unit tests for DataSanitizer with mocked PII service.

These tests focus on DataSanitizer's core logic (data structure traversal,
credential detection, K8s resource handling) without loading the spaCy model.
"""

import pytest

from services.data_sanitizer import REDACTED_VALUE, DataSanitizer
from utils.pii_detector import PIIDetector
from utils.singleton_meta import SingletonMeta


class MockPIIService:
    """Mock PII service for testing without spaCy model."""

    def clean(self, text: str) -> str:
        """Mock PII detection that replaces known test values."""
        if not text:
            return text

        # Mock simple PII replacements for testing
        replacements = {
            "john@example.com": "{{EMAIL}}",
            "admin@example.com": "{{EMAIL}}",
            "john.doe@example.com": "{{EMAIL}}",
            "555-123-4567": "{{PHONE}}",
            "(555) 123-4567": "{{PHONE}}",
            "1800 555-5555": "{{PHONE}}",
            "+49 555 1234567": "{{PHONE}}",
            "123-45-6789": "{{SOCIAL_SECURITY_NUMBER}}",
            "4111-1111-1111-1111": "{{CREDIT_CARD}}",
        }

        result = text
        for pii, token in replacements.items():
            result = result.replace(pii, token)
        return result


class TestDataSanitizerUnit:
    """Unit tests for DataSanitizer with mocked PII service."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset DataSanitizer and setup with mocked PII service."""
        # Reset both to inject mock - DataSanitizer will create new instance with mock
        # PIIDetector reset is needed here because we're injecting a mock service
        SingletonMeta.reset_instance(PIIDetector)
        SingletonMeta.reset_instance(DataSanitizer)
        # Create with mock PII service
        self.mock_pii = MockPIIService()
        self.data_sanitizer = DataSanitizer(pii_service=self.mock_pii)
        yield
        # Clean up - reset PIIDetector so next test suite gets real one
        SingletonMeta.reset_instance(DataSanitizer)
        SingletonMeta.reset_instance(PIIDetector)

    def test_basic_dict_traversal(self):
        """Test that DataSanitizer correctly traverses nested dictionaries."""
        data = {
            "username": "admin",
            "password": "secret123",
            "settings": {
                "api_key": "key456",
                "database": {
                    "host": "localhost",
                    "password": "db-password",
                },
            },
        }

        result = self.data_sanitizer.sanitize(data)

        # Credentials should be redacted
        assert result["username"] == REDACTED_VALUE
        assert result["password"] == REDACTED_VALUE
        assert result["settings"]["api_key"] == REDACTED_VALUE
        assert result["settings"]["database"]["password"] == REDACTED_VALUE
        # Non-sensitive fields should remain
        assert result["settings"]["database"]["host"] == "localhost"

    def test_list_handling(self):
        """Test that DataSanitizer correctly handles lists."""
        data = [
            {"name": "app1", "api_key": "key1"},
            {"name": "app2", "secret": "secret2"},
        ]

        result = self.data_sanitizer.sanitize(data)

        expected_length = 2
        assert len(result) == expected_length
        assert result[0]["api_key"] == REDACTED_VALUE
        assert result[1]["secret"] == REDACTED_VALUE
        assert result[0]["name"] == "app1"
        assert result[1]["name"] == "app2"

    def test_pii_detection_integration(self):
        """Test that PII service is called correctly."""
        data = {
            "email": "john@example.com",
            "phone": "555-123-4567",
            "description": "Contact john@example.com",
        }

        result = self.data_sanitizer.sanitize(data)

        # PII should be detected by mock service
        assert result["email"] == "{{EMAIL}}"
        assert result["phone"] == "{{PHONE}}"
        assert "{{EMAIL}}" in result["description"]

    def test_mixed_credentials_and_pii(self):
        """Test handling of both credentials and PII in same structure."""
        data = {
            "username": "admin",
            "password": "secret123",
            "contact_email": "admin@example.com",
            "contact_phone": "555-123-4567",
        }

        result = self.data_sanitizer.sanitize(data)

        # Credentials redacted
        assert result["username"] == REDACTED_VALUE
        assert result["password"] == REDACTED_VALUE
        # PII detected
        assert result["contact_email"] == "{{EMAIL}}"
        assert result["contact_phone"] == "{{PHONE}}"

    def test_k8s_configmap_structure(self):
        """Test sanitization of K8s ConfigMap structure."""
        data = {
            "kind": "ConfigMap",
            "metadata": {"name": "my-config"},
            "data": {
                "username": "admin",
                "password": "secret",
                "email": "john.doe@example.com",
            },
        }

        result = self.data_sanitizer.sanitize(data)

        assert result["kind"] == "ConfigMap"
        assert result["metadata"]["name"] == "my-config"
        assert result["data"]["username"] == REDACTED_VALUE
        assert result["data"]["password"] == REDACTED_VALUE
        assert result["data"]["email"] == "{{EMAIL}}"

    def test_deeply_nested_structure(self):
        """Test handling of deeply nested data structures."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "password": "deep-secret",
                        "email": "admin@example.com",
                    }
                }
            }
        }

        result = self.data_sanitizer.sanitize(data)

        assert result["level1"]["level2"]["level3"]["password"] == REDACTED_VALUE
        assert result["level1"]["level2"]["level3"]["email"] == "{{EMAIL}}"

    def test_string_sanitization(self):
        """Test sanitization of raw strings."""
        text = "Contact john@example.com or call 555-123-4567. Password: secret123"

        result = self.data_sanitizer.sanitize(text)

        # PII should be replaced
        assert "{{EMAIL}}" in result
        assert "{{PHONE}}" in result
        assert "john@example.com" not in result
        # Credentials should be redacted
        assert "{{REDACTED}}" in result
        assert "secret123" not in result

    def test_list_of_strings(self):
        """Test sanitization of list containing strings."""
        data = [
            "Contact: john@example.com",  # PII detection
            "Password: secret123",  # Credential regex
            {"name": "test-value"},  # Dict passthrough
        ]

        result = self.data_sanitizer.sanitize(data)

        assert "{{EMAIL}}" in result[0]
        assert "john@example.com" not in result[0]
        assert "{{REDACTED}}" in result[1]
        assert "secret123" not in result[1]
        assert result[2]["name"] == "test-value"

    def test_sensitive_field_exclusion(self):
        """Test that configured fields are excluded from sanitization."""
        data = {
            "secretName": "my-secret-reference",  # Should NOT be redacted
            "secret_key": "actual-secret",  # Should be redacted
        }

        result = self.data_sanitizer.sanitize(data)

        # secretName is in DEFAULT_SENSITIVE_FIELD_TO_EXCLUDE
        assert result["secretName"] == "my-secret-reference"
        assert result["secret_key"] == REDACTED_VALUE

    def test_empty_data_handling(self):
        """Test handling of empty data structures."""
        assert self.data_sanitizer.sanitize({}) == {}
        assert self.data_sanitizer.sanitize([]) == []
        assert self.data_sanitizer.sanitize("") == ""

    def test_invalid_input_type(self):
        """Test that invalid input types raise ValueError."""
        with pytest.raises(ValueError, match="Data must be a string or list or dictionary"):
            self.data_sanitizer.sanitize(123)

        with pytest.raises(ValueError, match="Data must be a string or list or dictionary"):
            self.data_sanitizer.sanitize(None)

    def test_pii_service_injection(self):
        """Test that the injected PII service is used."""
        # Verify our mock is being used
        assert self.data_sanitizer.pii_detector is self.mock_pii

        # Verify it's actually called
        result = self.data_sanitizer.sanitize("email: john@example.com")
        assert "{{EMAIL}}" in result
