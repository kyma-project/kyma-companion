from typing import List

from pydantic import BaseModel

from tests.blackbox.evaluation.src.models.evaluation import Evaluation

from tests.blackbox.evaluation.src.models.enums import Complexity, Category


class Resource(BaseModel):
    """
    Resource represents a K8s resource.
    """

    type: str
    name: str
    namespace: str


class Expectation(BaseModel):
    """
    Expectation represents a single expectation with a statement, a list of categories,
    a description, and a complexity.
    """

    name: str
    statement: str
    categories: List[Category]
    complexity: Complexity


class Scenario(BaseModel):
    """Scenario is a class that contains the information of a Kyma companion test scenario."""

    id: str
    description: str
    expectations: List[Expectation]
    evaluation: Evaluation = Evaluation()


class ScenarioList(BaseModel):
    """ScenarioDict is a list that contains scenarios."""

    items: List[Scenario] = []

    def add(self, item: Scenario) -> None:
        self.items.append(item)
