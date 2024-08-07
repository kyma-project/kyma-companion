"""This module contains the Expectation class and the ExpectationDict class."""

from typing import List
from pydantic import BaseModel, PositiveInt
from src.models.evaluation.category import Category


class Expectation(BaseModel):
    """
    Expectation represents a single expectation with a unique expectation_id,
    a description, and a weight.
    """

    expectation_id: str
    statement: str
    categories: List[Category]
    weight: PositiveInt = 1


class ExpectationList(BaseModel):
    """ExpectationList is a list of expectations."""

    items: List[Expectation]

    def get_expectation(self, expectation_id: str) -> Expectation:
        """Get the expectation by its ID."""
        if self.items is None or len(self.items) == 0:
            raise ValueError("No expectations found in the list.")

        for expectation in self.items:
            if expectation.expectation_id == expectation_id:
                return expectation

        raise ValueError(f"Expectation ID {expectation_id} not found in expectations.")
