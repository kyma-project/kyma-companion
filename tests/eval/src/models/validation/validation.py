"""Validation is a class that contains the information for the
validation of a model for its fit for evaluation of a scenario."""

from typing import List, Dict, Tuple

from pydantic import BaseModel
from termcolor import colored

from src.models.evaluation.scenario import Scenario
from src.models.validation.mock_response import MockResponseList
from src.models.evaluation.category import Category


class Validation(BaseModel):
    """Validation is a class that contains the information of a calibration."""

    scenario: Scenario
    mock_responses: MockResponseList

    def get_unique_categories_from_scenario(self) -> List[Category]:
        """Get the unique categories from the scenario."""
        return self.scenario.get_unique_categories()

    def get_score_per_category(self) -> Dict[Category, Tuple[int, int]]:
        """Get the score per category."""
        category_scores = {}
        for category in self.get_unique_categories_from_scenario():
            category_scores[category] = (0, 0)

        for mock_response in self.mock_responses.items:
            for wanted_result in mock_response.wanted_results.items:
                categories = self.scenario.expectations.get_expectation(
                    wanted_result.expectation_id
                ).categories
                for category in categories:
                    reached, possible = category_scores[category]
                    if wanted_result.does_match():
                        reached += wanted_result.weight
                    possible += wanted_result.weight
                    category_scores[category] = (reached, possible)

        return category_scores

    def print_score_per_category(self) -> None:
        """Print the score per category."""
        scores = self.get_score_per_category()
        for category, score in scores.items():
            print(colored(f"{category.name}: {score[0]}/{score[1]}", "green"))

    def get_score_per_mock_response_id(self) -> Dict[str, Tuple[int, int]]:
        """Get the reached and possible score for each mock response, by ID."""
        mock_response_scores = {}
        for mock_response in self.mock_responses.items:
            mock_response_scores[mock_response.mock_response_id] = (0, 0)

        for mock_response in self.mock_responses.items:
            for wanted_result in mock_response.wanted_results.items:
                reached, possible = mock_response_scores[mock_response.mock_response_id]
                if wanted_result.does_match():
                    reached += wanted_result.weight
                possible += wanted_result.weight
                mock_response_scores[mock_response.mock_response_id] = (
                    reached,
                    possible,
                )

        return mock_response_scores

    def print_score_per_mock_response(self) -> None:
        """Print the score per mock response."""
        scores = self.get_score_per_mock_response_id()
        for mock_response_id, score in scores.items():
            mock_response = self.mock_responses.get_mock_response(mock_response_id)
            print(
                colored(
                    f"{mock_response.mock_response_content}: {score[0]}/{score[1]}",
                    "green",
                )
            )
