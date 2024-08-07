"""
This module contains classes to represent the result of
comparing an expectation with an assistant response.
"""

from typing import List
from pydantic import BaseModel


class EvaluationResult(BaseModel):
    """ValidationResult is a class that stores the result of comparing
    an expectation with a assistant_response."""

    expectation_id: str
    assistant_response_id: str
    was_matched: bool


class EvaluationResultList(BaseModel):
    """ValidationResultList is a class that contains a list of validation results."""

    items: List[EvaluationResult]

    def add_new_evaluation_result(
        self, expectation_id: str, assistant_response_id: str, was_matched: bool
    ) -> None:
        """Add a new evaluation result to the list."""
        self.items.append(
            EvaluationResult(
                expectation_id=expectation_id,
                assistant_response_id=assistant_response_id,
                was_matched=was_matched,
            )
        )
