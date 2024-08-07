"""This module contains the WantedResult class and WantedResultList class."""

from typing import List, Optional

from pydantic import BaseModel, PositiveInt


class WantedResult(BaseModel):
    """WantedResult is a class that contains the information of a wanted result."""

    expectation_id: str
    wanted_result: bool
    actual_result: Optional[bool] = None
    weight: PositiveInt = 1

    def set_actual_result(self, result: bool) -> None:
        """Sets the actual result for a wanted result."""
        self.actual_result = result

    def does_match(self) -> bool:
        """Returns True if the actual result matches the wanted result."""
        return self.wanted_result == self.actual_result

    def has_actual_result(self) -> bool:
        """Returns True if the wanted result has an actual result."""
        return self.actual_result is not None


class WantedResultList(BaseModel):
    """WantedResultDict is a dictionary that contains wanted results."""

    items: List[WantedResult]

    def has_actual_result(self, expectation_id: str) -> bool:
        """Returns True if the wanted result has an actual result."""
        for wanted_result in self.items:
            if wanted_result.expectation_id == expectation_id:
                return wanted_result.has_actual_result()
        raise ValueError(
            f"Expectation ID {expectation_id} not found in wanted results."
        )

    def get_wanted_result(self, expectation_id: str) -> Optional[WantedResult]:
        """Get the wanted result by its ID."""
        for wanted_result in self.items:
            if wanted_result.expectation_id == expectation_id:
                return wanted_result
        raise ValueError(
            f"Expectation ID {expectation_id} not found in wanted results."
        )

    def add_new_wanted_result(self, expectation_id: str, wanted_result: bool) -> None:
        """Adds a new wanted result to the items."""
        self.items.append(
            WantedResult(
                expectation_id=expectation_id,
                wanted_result=wanted_result,
                actual_result=None,
            )
        )

    def set_actual_result(self, expectation_id: str, result: bool) -> None:
        """Sets the actual result for a wanted result."""
        for wanted_result in self.items:
            if wanted_result.expectation_id == expectation_id:
                wanted_result.set_actual_result(result)
                return
        raise ValueError(
            f"Expectation ID {expectation_id} not found in wanted results."
        )

    def does_match(self, expectation_id: str) -> bool:
        """Returns True if the actual result matches the wanted result."""
        for wanted_result in self.items:
            if wanted_result.expectation_id == expectation_id:
                return wanted_result.does_match()
        raise ValueError(
            f"Expectation ID {expectation_id} not found in wanted results."
        )
