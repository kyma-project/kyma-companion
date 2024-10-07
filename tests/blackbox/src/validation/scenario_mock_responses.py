from common.logger import get_logger

# TODO: Import as Evaluation
from evaluation.scenario.scenario import Scenario
from pydantic import BaseModel

logger = get_logger(__name__)


class ExpectedEvaluation(BaseModel):
    scenario_expectation_name: str
    expected_evaluation: bool


class MockResponse(BaseModel):
    description: str
    scenario_id: str
    mock_response_content: str
    expected_evaluations: list[ExpectedEvaluation]


class ValidationScenario(BaseModel):
    # TODO: rename to simply evaluation
    evaluation_scenario: Scenario
    mock_responses: list[MockResponse]


class ScenarioScore(BaseModel):
    scenario_id: str
    max_score: int
    score: int
    max_success: int
    success: int
    mock_response_count: int
    report: str
