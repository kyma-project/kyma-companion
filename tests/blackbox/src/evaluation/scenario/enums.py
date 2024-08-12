from enum import IntEnum, StrEnum


class TestStatus(StrEnum):
    """Category represents enum for the category of an expectation."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    COMPLETED = "completed"


class Complexity(IntEnum):
    """Category represents enum for the category of an expectation."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3

    def to_string(self) -> str:
        """Convert the complexity to a string."""
        names = {1: "low", 2: "medium", 3: "high"}
        return names[self]


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