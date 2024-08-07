"""
This module contains classes to represent a test scenario for 
the evaluation of an AI assistant.
"""

from typing import List, Dict, Tuple
from uuid import uuid4

from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from termcolor import colored

from src.models.evaluation.expectation import ExpectationList
from src.models.evaluation.category import Category
from src.models.evaluation.evaluation_result import EvaluationResultList
from src.logic.utils import print_seperator_line


class Scenario(BaseModel):
    """Scenario is a class that contains the information of a AI assistant test scenario."""

    scenario_id: str
    problem: str
    expectations: ExpectationList
    _assistant_responses: Dict[str, BaseMessage] = {}
    evaluation_results: EvaluationResultList = EvaluationResultList(items=[])

    def no_response_error(self) -> ValueError:
        """Error to raise when there is no response."""
        return ValueError("The scenario does not have any responses.")

    def no_results_error(self) -> ValueError:
        """Error to raise when there are no results."""
        return ValueError("The scenario does not have any evaluation results.")

    def get_expectation(self, expectation_id: str):
        """Get the expectation by its ID."""
        return self.expectations.get_expectation(expectation_id)

    def has_response(self) -> bool:
        """Check if the scenario has a response."""
        return (
            self.assistant_responses is not None
            and len(self.assistant_responses) > 0
        )

    def add_new_assistant_response(self, base_message: BaseMessage) -> None:
        """Add a new assistant response to the scenario."""
        assistant_response_id = uuid4().hex
        self._assistant_responses[assistant_response_id] = base_message

    def get_assistant_response(self, assistant_response_id: str) -> BaseMessage:
        """Get the assistant response by its ID."""
        return self._assistant_responses[assistant_response_id]

    @property
    def assistant_responses(self) -> List[Tuple[str, BaseMessage]]:
        """Get the assistant responses."""
        return [
            (assistant_response_id, base_message)
            for assistant_response_id, base_message in self._assistant_responses.items()
        ]

    def add_new_evaluation_result(
        self, expectation_id: str, assistant_response_id: str, was_matched: bool
    ) -> None:
        """Add a new evaluation result to the scenario."""
        if self.evaluation_results is None:
            self.evaluation_results = EvaluationResultList(items=[])
        self.evaluation_results.add_new_evaluation_result(
            expectation_id, assistant_response_id, was_matched
        )

    def get_reached_score(self) -> int:
        """Computes the reached score via the scenario."""
        if self.evaluation_results is None or len(self.evaluation_results.items) == 0:
            raise self.no_results_error()

        score = 0
        for result in self.evaluation_results.items:
            expectation = self.expectations.get_expectation(result.expectation_id)
            if expectation is None:
                raise ValueError(
                    f"Expectation ID {result.expectation_id} not found in expectations."
                )
            if result.was_matched:
                score += expectation.weight
        return score

    def get_possible_score(self) -> int:
        """Computes the total amount of reachable score points."""
        if self.expectations is None or len(self.expectations.items) == 0:
            raise ValueError("The scenario does not have any expectations.")

        score = 0
        for expectation in self.expectations.items:
            score += expectation.weight
        return score

    def get_unique_categories(self) -> List[Category]:
        """Returns a list of all uniqe categories."""
        categories = []
        for expectation in self.expectations.items:
            for category in expectation.categories:
                if category not in categories:
                    categories.append(category)
        return categories

    def get_scores_by_category(self) -> Dict[Category, Tuple[int, int]]:
        """Computes the reached and possible score for each
        category and returns it as a dictionary,
        where the key is the category and the value
        is a tuple of reached and possible score."""
        category_scores = {}
        for category in self.get_unique_categories():
            category_scores[category] = (0, 0)
        
        for expectation in self.expectations.items:
            for category in expectation.categories:
                reached, possible = category_scores[category]
                reached += expectation.weight if expectation.weight is not None else 0
                possible += expectation.weight if expectation.weight is not None else 0
                category_scores[category] = (reached, possible)
        
        return category_scores


class ScenarioList(BaseModel):
    """ScenarioDict is a list that contains scenarios."""

    items: List[Scenario]

    def get_unique_categories(self) -> List[Category]:
        """Returns a list of all uniqe categories."""
        categories = []
        for scenario in self.items:
            for expectation in scenario.expectations.items:
                for category in expectation.categories:
                    if category not in categories:
                        categories.append(category)
        return categories

    def get_scores_by_category(self) -> Dict[Category, Tuple[int, int]]:
        """Computes the reached and possible score for each
        category and returns it as a dictionary,
        where the key is the category and the value
        is a tuple of reached and possible score."""
        category_scores = {}
        for category in self.get_unique_categories():
            category_scores[category] = (0, 0)
        for scenario in self.items:
            for category, scores in scenario.get_scores_by_category().items():
                reached, possible = category_scores[category]
                reached += scores[0]
                possible += scores[1]
                category_scores[category] = (reached, possible)
        return category_scores

    def print_scores_by_category(self) -> None:
        """Prints the reached and possible score for each category."""
        print_seperator_line()
        print(colored("Scores by category:", "red"))
        category_scores = self.get_scores_by_category()
        for category, scores in category_scores.items():
            print(colored(f"{category.name}: {scores[0]}/{scores[1]}", "green"))
        print_seperator_line()

    def get_scores_by_scenario_id(self) -> Dict[str, Tuple[int, int]]:
        """Computes the reached and possible score for each
        scenario and returns it as a dictionary,
        where the key is the scenario ID and the value
        is a tuple of reached and possible score."""
        scenario_scores = {}
        for scenario in self.items:
            reached = scenario.get_reached_score()
            possible = scenario.get_possible_score()
            scenario_scores[scenario.scenario_id] = (reached, possible)
        return scenario_scores

    def print_scores_by_scenario(self) -> None:
        """Prints the reached and possible score for each scenario."""

        print_seperator_line()
        print(colored("Scores by Scenario:", "red"))
        scenario_scores = self.get_scores_by_scenario_id()
        for scenario_id, scores in scenario_scores.items():
            print(colored(f"{scenario_id}: {scores[0]}/{scores[1]}", "green"))
        print_seperator_line()
