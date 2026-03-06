"""PII detection using Microsoft Presidio.

This module provides a PIIDetector class that replaces the unmaintained
scrubadub library with Microsoft's Presidio framework for PII detection.

Presidio is an enterprise-grade, extensible PII detection and anonymization
framework with ML-based context awareness.

References:
- Presidio: https://github.com/microsoft/presidio
- Documentation: https://microsoft.github.io/presidio/
"""

from typing import cast

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.entities.engine.recognizer_result import RecognizerResult as AnonymizerRecognizerResult


class PIIDetector:
    """PII detector using Microsoft Presidio.

    Replaces personally identifiable information with tokens like {{EMAIL}}.
    Compatible with scrubadub.Scrubber() interface.

    Uses Presidio to detect:
    - EMAIL_ADDRESS
    - PHONE_NUMBER
    - CREDIT_CARD
    - US_SSN (US Social Security Number)

    And potentially more PII types that Presidio supports out of the box.
    """

    def __init__(self):
        """Initialize the PII detector with Presidio engines.

        Creates:
        - AnalyzerEngine: Detects PII in text with small spaCy model (13MB)
        - AnonymizerEngine: Anonymizes/redacts detected PII

        Note: Uses en_core_web_sm (small model) to keep Docker image small.
        """
        # Initialize Presidio engines with default NLP (uses en_core_web_sm)
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

        # Define the PII entities we want to detect
        # Maps Presidio entity types to our output token format
        self.entity_mapping: dict[str, str] = {
            "EMAIL_ADDRESS": "EMAIL",
            "PHONE_NUMBER": "PHONE",
            "CREDIT_CARD": "CREDIT_CARD",
            "US_SSN": "SOCIAL_SECURITY_NUMBER",
        }

        # Presidio entities to detect (keys from mapping)
        self.entities_to_detect: list[str] = list(self.entity_mapping.keys())

    def clean(self, text: str) -> str:
        """Detect and redact PII in text.

        Compatible with scrubadub.Scrubber().clean() interface.
        Returns text with PII replaced by {{TYPE}} tokens.

        Args:
            text: Input text potentially containing PII.

        Returns:
            Sanitized text with PII replaced by tokens like {{EMAIL}}.
        """
        if not text:
            return text

        # Analyze text for PII
        analyzer_results = self.analyzer.analyze(
            text=text,
            entities=self.entities_to_detect,
            language="en",
        )

        # If no PII found, return original text
        if not analyzer_results:
            return text

        # Create operator configurations for each detected entity type
        # This tells the anonymizer how to replace each PII type
        operators = {}
        for result in analyzer_results:
            entity_type = result.entity_type
            if entity_type in self.entity_mapping:
                # Replace with our token format: {{TYPE}}
                token = f"{{{{{self.entity_mapping[entity_type]}}}}}"
                operators[entity_type] = OperatorConfig("replace", {"new_value": token})

        # Anonymize the text using the operators
        # Cast analyzer results to anonymizer's RecognizerResult type
        # (they are compatible at runtime, just different type definitions)
        anonymized_result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=cast(list[AnonymizerRecognizerResult], analyzer_results),
            operators=operators,
        )

        return str(anonymized_result.text)
