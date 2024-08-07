from enum import StrEnum


class TestStatus(StrEnum):
    """Category represents enum for the category of an expectation."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


class Complexity(StrEnum):
    """Category represents enum for the category of an expectation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def to_int(self) -> int:
        if self == Complexity.LOW:
            return 1
        if self == Complexity.MEDIUM:
            return 2
        if self == Complexity.HIGH:
            return 3
        raise ValueError(f"Invalid complexity: {self}")


class Category(StrEnum):
    """Category represents enum for the category of an expectation."""

    COMPLETENESS = "completeness"
    PARTIAL_ANSWER = "partial_answer"
    KYMA = "kyma"
    KUBERNETES = "kubernetes"
    OTHER = "other"
    PROBLEM_FINDING = "problem_finding"
    SOLUTION_FINDING = "solution_finding"
    GENERAL_INQUIRY = "general_inquiry"
    STEP_BY_STEP_GUIDANCE = "step-by-step_guidance"
    DEFINITION_OR_EXPLANATION = "definition/explanation"
    YAML = "yaml"
