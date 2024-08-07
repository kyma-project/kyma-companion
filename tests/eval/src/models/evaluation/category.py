"""This module contains the Category enum class."""

from enum import Enum


class Category(Enum):
    """Category represents the category of an expectation."""

    PLAIN_K8S = 1
    KYMA = 2
    YAML = 3
    PROBLEM_FINDING = 4
    SOLUTION_FINDING = 5

    def to_string(self) -> str:
        """Returns the string representation of the category."""
        if self == Category.PLAIN_K8S:
            return "Plain Kubernetes"
        if self == Category.KYMA:
            return "Kyma"
        if self == Category.YAML:
            return "yaml"
        if self == Category.PROBLEM_FINDING:
            return "problem finding"
        if self == Category.SOLUTION_FINDING:
            return "solution finding"

        return "Unknown"
