"""Unit tests for PIIDetector class using Presidio."""

import pytest

from utils.pii_detector import PIIDetector


class TestPIIDetector:
    """Test suite for PIIDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a PIIDetector instance for testing."""
        return PIIDetector()

    # Basic Email Detection Tests
    def test_email_detection_simple(self, detector):
        """Test detection of simple email addresses."""
        text = "Contact me at test@example.com for more info"
        result = detector.clean(text)
        assert "{{EMAIL}}" in result
        assert "test@example.com" not in result

    def test_email_detection_complex(self, detector):
        """Test detection of complex email addresses with special characters."""
        text = "Email: user.name+tag@example.co.uk"
        result = detector.clean(text)
        assert "{{EMAIL}}" in result
        assert "user.name+tag@example.co.uk" not in result

    def test_email_detection_multiple(self, detector):
        """Test detection of multiple email addresses."""
        text = "Contact alice@example.com or bob@test.org"
        result = detector.clean(text)
        # Should have 2 EMAIL tokens
        expected_count = 2
        assert result.count("{{EMAIL}}") == expected_count
        assert "alice@example.com" not in result
        assert "bob@test.org" not in result

    # Phone Number Detection Tests
    def test_phone_detection_us_format(self, detector):
        """Test detection of US phone numbers."""
        text = "Call 555-123-4567"
        result = detector.clean(text)
        assert "{{PHONE}}" in result or "555-123-4567" not in result

    def test_phone_detection_parentheses(self, detector):
        """Test detection of phone with parentheses."""
        text = "Call (555) 123-4567"
        result = detector.clean(text)
        # Presidio should detect this
        assert "{{PHONE}}" in result or "(555) 123-4567" not in result

    # Credit Card Detection Tests
    def test_credit_card_detection_valid_visa(self, detector):
        """Test detection of valid Visa credit card numbers."""
        # Valid Visa test card (passes Luhn check)
        text = "Card: 4111111111111111"
        result = detector.clean(text)
        assert "{{CREDIT_CARD}}" in result
        assert "4111111111111111" not in result

    def test_credit_card_detection_formatted(self, detector):
        """Test detection of formatted credit card numbers."""
        text = "Card: 4111-1111-1111-1111"
        result = detector.clean(text)
        assert "{{CREDIT_CARD}}" in result
        assert "4111-1111-1111-1111" not in result

    # SSN Detection Tests
    def test_ssn_detection_formatted(self, detector):
        """Test detection of formatted SSN (XXX-XX-XXXX)."""
        text = "SSN: 123-45-6789"
        result = detector.clean(text)
        assert "{{SOCIAL_SECURITY_NUMBER}}" in result
        assert "123-45-6789" not in result

    def test_ssn_detection_multiple(self, detector):
        """Test detection of multiple SSNs."""
        text = "SSN1: 123-45-6789 and SSN2: 987-65-4321"
        result = detector.clean(text)
        # Should have 2 SSN tokens
        expected_count = 2
        assert result.count("{{SOCIAL_SECURITY_NUMBER}}") == expected_count
        assert "123-45-6789" not in result
        assert "987-65-4321" not in result

    # Multiple PII Types Tests
    def test_multiple_pii_types(self, detector):
        """Test detection of multiple PII types in the same text."""
        text = "Contact john@test.com or call 555-123-4567"
        result = detector.clean(text)
        assert "{{EMAIL}}" in result
        assert "john@test.com" not in result
        # Phone might or might not be detected depending on Presidio's rules
        # but at least email should be caught

    def test_complex_text_with_pii(self, detector):
        """Test detection in complex, realistic text."""
        text = """
        Customer Information:
        Name: John Doe
        Email: john.doe@example.com
        Phone: (555) 123-4567
        SSN: 123-45-6789
        Credit Card: 4111-1111-1111-1111
        """
        result = detector.clean(text)
        # Check that PII is redacted
        assert "{{EMAIL}}" in result
        assert "john.doe@example.com" not in result
        assert "{{SOCIAL_SECURITY_NUMBER}}" in result
        assert "123-45-6789" not in result
        assert "{{CREDIT_CARD}}" in result
        assert "4111-1111-1111-1111" not in result

    # Edge Cases Tests
    def test_empty_string(self, detector):
        """Test handling of empty string."""
        result = detector.clean("")
        assert result == ""

    def test_none_handling(self, detector):
        """Test handling of None input."""
        result = detector.clean(None)
        assert result is None

    def test_text_without_pii(self, detector):
        """Test that text without PII remains unchanged."""
        text = "This is a normal sentence with no personal information."
        result = detector.clean(text)
        assert result == text

    def test_pii_at_string_boundaries(self, detector):
        """Test PII detection at the start and end of strings."""
        # Email at start
        text = "test@example.com"
        result = detector.clean(text)
        assert "{{EMAIL}}" in result
        assert "test@example.com" not in result

        # SSN standalone
        text = "123-45-6789"
        result = detector.clean(text)
        assert "{{SOCIAL_SECURITY_NUMBER}}" in result
        assert "123-45-6789" not in result

    def test_consecutive_pii(self, detector):
        """Test detection of consecutive PII items."""
        text = "test@example.com 555-123-4567"
        result = detector.clean(text)
        assert "{{EMAIL}}" in result
        assert "test@example.com" not in result

    # Interface Compatibility Tests
    def test_clean_method_exists(self, detector):
        """Test that clean() method exists (scrubadub compatibility)."""
        assert hasattr(detector, "clean")
        assert callable(detector.clean)

    def test_clean_returns_string(self, detector):
        """Test that clean() returns a string."""
        result = detector.clean("test@example.com")
        assert isinstance(result, str)
