"""PII detection using Microsoft Presidio.

This module provides a PIIDetector class that replaces the unmaintained
scrubadub library with Microsoft's Presidio framework for PII detection.

Presidio is an enterprise-grade, extensible PII detection and anonymization
framework with ML-based context awareness.

References:
- Presidio: https://github.com/microsoft/presidio
- Documentation: https://microsoft.github.io/presidio/
"""

from typing import Protocol, cast

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.entities.engine.recognizer_result import RecognizerResult as AnonymizerRecognizerResult

from utils.singleton_meta import SingletonMeta


class PIIService(Protocol):
    """Protocol for PII detection services.

    This protocol defines the interface that any PII detection service must implement.
    Used for dependency injection to make services testable without loading the spaCy model.
    """

    def clean(self, text: str) -> str:
        """Detect and redact PII in text.

        Args:
            text: Input text potentially containing PII.

        Returns:
            Sanitized text with PII replaced by tokens like {{EMAIL}}.
        """
        ...


class PIIDetector(metaclass=SingletonMeta):
    """PII detector using Microsoft Presidio.

    Replaces personally identifiable information with tokens like {{EMAIL}}.
    Compatible with scrubadub.Scrubber() interface.

    Uses SingletonMeta to avoid loading spaCy model multiple times.
    This dramatically reduces memory usage (from 64GB to <1GB in tests).

    Uses Presidio to detect:
    - EMAIL_ADDRESS
    - PHONE_NUMBER
    - CREDIT_CARD
    - US_SSN (US Social Security Number)

    And potentially more PII types that Presidio supports out of the box.
    """

    def __init__(self):
        """Initialize the PII detector with Presidio engines.

        Uses SingletonMeta to avoid loading spaCy model multiple times.
        This dramatically reduces memory usage (from 64GB to <1GB in tests).

        Creates:
        - AnalyzerEngine: Detects PII in text with small spaCy model (13MB)
        - AnonymizerEngine: Anonymizes/redacts detected PII

        Note: Uses en_core_web_sm (small model) to keep Docker image small.
        Uses custom SSN recognizer to match scrubadub's behavior (no strict validation).
        """
        # Create custom SSN recognizer that matches scrubadub's behavior
        # Presidio's default UsSsnRecognizer is too strict and rejects many valid test SSNs
        ssn_recognizer = PatternRecognizer(
            supported_entity="US_SSN",
            patterns=[
                # XXX-XX-XXXX format (medium confidence)
                Pattern(
                    name="SSN formatted",
                    regex=r"\b\d{3}-\d{2}-\d{4}\b",
                    score=0.5,
                ),
                # XXXXXXXXX format (weak confidence)
                Pattern(
                    name="SSN unformatted",
                    regex=r"\b\d{9}\b",
                    score=0.1,
                ),
            ],
            context=["ssn", "social security"],
        )

        # Create registry with custom recognizers
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(languages=["en"])

        # Remove the default US_SSN recognizer and add our custom one
        registry.remove_recognizer("UsSsnRecognizer")
        registry.add_recognizer(ssn_recognizer)

        # Initialize Presidio engines
        self.analyzer = AnalyzerEngine(registry=registry)
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
        # Use lower score threshold (0.01) to catch US_SSN which has weak regex patterns (0.05)
        # without context. This matches scrubadub's behavior of detecting SSN patterns.
        analyzer_results = self.analyzer.analyze(
            text=text,
            entities=self.entities_to_detect,
            language="en",
            score_threshold=0.01,
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
