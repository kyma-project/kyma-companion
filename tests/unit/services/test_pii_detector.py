"""Tests for PII detection and scrubbing (email, phone, CC, SSN)."""

import pytest

from services.pii_detector import (
    REDACTED_CC,
    REDACTED_EMAIL,
    REDACTED_PHONE,
    REDACTED_SSN,
    detect_pii,
    scrub_pii,
)


class TestDetectPII:
    """Tests for detect_pii function."""

    @pytest.mark.parametrize(
        "text, expected_type, expected_match",
        [
            ("Contact me at user@example.com", REDACTED_EMAIL, "user@example.com"),
            ("Email: first.last+tag@sub.domain.co.uk", REDACTED_EMAIL, "first.last+tag@sub.domain.co.uk"),
            ("reach out to admin@localhost.org please", REDACTED_EMAIL, "admin@localhost.org"),
        ],
    )
    def test_detect_email(self, text: str, expected_type: str, expected_match: str):
        results = detect_pii(text)
        matches = [r for r in results if r["type"] == expected_type]
        assert len(matches) >= 1
        assert any(m["match"] == expected_match for m in matches)

    @pytest.mark.parametrize(
        "text, expected_match",
        [
            ("Call me at +1-555-123-4567", "+1-555-123-4567"),
            ("US number 555-123-4567", "555-123-4567"),
            ("Intl: +44 20 7946 0958", "+44 20 7946 0958"),
            ("US number 555.123.4567", "555.123.4567"),
        ],
    )
    def test_detect_phone(self, text: str, expected_match: str):
        results = detect_pii(text)
        matches = [r for r in results if r["type"] == REDACTED_PHONE]
        assert len(matches) >= 1
        assert any(m["match"] == expected_match for m in matches)

    @pytest.mark.parametrize(
        "text, expected_match",
        [
            ("Visa: 4111111111111111", "4111111111111111"),
            ("MC: 5500 0000 0000 0004", "5500 0000 0000 0004"),
            ("Amex: 371-449635-98431", "371-449635-98431"),
            ("Discover: 6011111111111117", "6011111111111117"),
            ("Visa dashed: 4111-1111-1111-1111", "4111-1111-1111-1111"),
        ],
    )
    def test_detect_credit_card(self, text: str, expected_match: str):
        results = detect_pii(text)
        matches = [r for r in results if r["type"] == REDACTED_CC]
        assert len(matches) >= 1
        assert any(m["match"] == expected_match for m in matches)

    @pytest.mark.parametrize(
        "text, expected_match",
        [
            ("SSN: 123-45-6789", "123-45-6789"),
            ("SSN: 123 45 6789", "123 45 6789"),
            ("SSN: 123456789", "123456789"),
        ],
    )
    def test_detect_ssn(self, text: str, expected_match: str):
        results = detect_pii(text)
        matches = [r for r in results if r["type"] == REDACTED_SSN]
        assert len(matches) >= 1
        assert any(m["match"] == expected_match for m in matches)

    def test_detect_no_pii(self):
        """Text with no PII returns empty list."""
        results = detect_pii("Hello world, this is a normal sentence.")
        assert results == []

    def test_detect_multiple_pii_types(self):
        """Text with multiple PII types returns all of them."""
        text = "Email user@test.com, SSN 123-45-6789, card 4111111111111111"
        results = detect_pii(text)
        types_found = {r["type"] for r in results}
        assert REDACTED_EMAIL in types_found
        assert REDACTED_SSN in types_found
        assert REDACTED_CC in types_found

    def test_detect_returns_correct_positions(self):
        """Detected PII includes start and end positions."""
        text = "Email: user@test.com"
        results = detect_pii(text)
        email_match = [r for r in results if r["type"] == REDACTED_EMAIL][0]
        assert email_match["start"] == 7
        assert email_match["end"] == 20
        assert text[email_match["start"] : email_match["end"]] == "user@test.com"

    def test_detect_empty_string(self):
        assert detect_pii("") == []


class TestScrubPII:
    """Tests for scrub_pii function."""

    def test_scrub_email(self):
        assert scrub_pii("Contact user@example.com") == f"Contact {REDACTED_EMAIL}"

    def test_scrub_phone(self):
        result = scrub_pii("Call +1-555-123-4567")
        assert REDACTED_PHONE in result
        assert "+1-555-123-4567" not in result

    def test_scrub_credit_card(self):
        result = scrub_pii("Card: 4111111111111111")
        assert REDACTED_CC in result
        assert "4111111111111111" not in result

    def test_scrub_ssn(self):
        result = scrub_pii("SSN: 123-45-6789")
        assert REDACTED_SSN in result
        assert "123-45-6789" not in result

    def test_scrub_multiple_pii(self):
        text = "Email: user@test.com, SSN: 123-45-6789"
        result = scrub_pii(text)
        assert REDACTED_EMAIL in result
        assert REDACTED_SSN in result
        assert "user@test.com" not in result
        assert "123-45-6789" not in result

    def test_scrub_no_pii(self):
        text = "No PII here."
        assert scrub_pii(text) == text

    def test_scrub_empty_string(self):
        assert scrub_pii("") == ""

    def test_scrub_preserves_surrounding_text(self):
        text = "Before user@test.com after"
        result = scrub_pii(text)
        assert result == f"Before {REDACTED_EMAIL} after"

    @pytest.mark.parametrize(
        "description, text",
        [
            ("SSN invalid area 000", "000-12-3456"),
            ("SSN invalid area 666", "666-12-3456"),
            ("SSN invalid group 00", "123-00-6789"),
            ("SSN invalid serial 0000", "123-45-0000"),
        ],
    )
    def test_scrub_does_not_match_invalid_ssn(self, description: str, text: str):
        """Invalid SSN formats should not be scrubbed."""
        result = scrub_pii(text)
        assert REDACTED_SSN not in result, f"Failed: {description}"

    def test_cc_before_ssn_ordering(self):
        """Credit cards should be matched before SSNs to avoid partial matches."""
        # A 16-digit CC number should not be detected as two SSNs.
        text = "Card: 4111111111111111"
        result = scrub_pii(text)
        assert REDACTED_CC in result
        # SSN should not appear in the result
        assert REDACTED_SSN not in result
