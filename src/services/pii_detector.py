"""Pure regex PII detection (email, phone, CC, SSN) replacing scrubadub."""

from __future__ import annotations

import re

# Compiled PII patterns
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

_PHONE_PATTERN = re.compile(
    r"(?<!\w)"  # not preceded by a word char (avoids matching inside hashes/tokens)
    r"(?:"
    r"\+1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"  # US/CA with +1 country code
    r"|"
    r"1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"  # US/CA with 1 prefix (e.g. 1-800-555-1234, 1800 555-5555)
    r"|"
    r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]?\d{4}"  # US/CA with separator (e.g. 555-123-4567, (555) 123-4567)
    r"|"
    r"\+\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"  # International with +
    r")"
    r"(?!\w)"  # not followed by a word char
)

_CC_PATTERN = re.compile(
    r"\b(?:"
    r"4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"  # Visa
    r"|"
    r"5[1-5]\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"  # Mastercard
    r"|"
    r"3[47]\d{1,2}[-\s]?\d{6}[-\s]?\d{5}"  # Amex (3-6-5 or 4-6-5 format)
    r"|"
    r"6(?:011|5\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"  # Discover
    r")\b"
)

_SSN_PATTERN = re.compile(r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b")

REDACTED_EMAIL = "{{EMAIL}}"
REDACTED_PHONE = "{{PHONE}}"
REDACTED_CC = "{{CREDIT_CARD}}"
REDACTED_SSN = "{{SOCIAL_SECURITY_NUMBER}}"

_ALL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (_CC_PATTERN, REDACTED_CC),
    (_SSN_PATTERN, REDACTED_SSN),
    (_EMAIL_PATTERN, REDACTED_EMAIL),
    (_PHONE_PATTERN, REDACTED_PHONE),
]


def detect_pii(text: str) -> list[dict]:
    """Detect PII in text and return list of matches.

    Returns:
        List of dicts with 'type', 'match', 'start', 'end' keys.
    """
    results = []
    for pattern, redacted_type in _ALL_PATTERNS:
        for match in pattern.finditer(text):
            results.append(
                {
                    "type": redacted_type,
                    "match": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    return results


def scrub_pii(text: str) -> str:
    """Replace all PII in text with redaction placeholders.

    Order matters: credit cards and SSNs are checked before phones
    to avoid partial matches.
    """
    for pattern, replacement in _ALL_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
