from typing import Protocol

from common.logger import get_logger
from langchain.prompts import PromptTemplate
from termcolor import colored

from validation.scenario_mock_responses import ScenarioScore, ValidationScenario
from validation.utils.models import Model
from validation.utils.utils import get_expectation, string_to_bool

logger = get_logger(__name__)

TEMPLATE = PromptTemplate(
    template="""Please only answer with one word, true or false:
    Does the given statement apply for the given text?
    The statement: '{statement}'. 
    The text: '{response}'
    Output: yes/no
    """,
    input_variables=["fact", "response"],
)


class Validator(Protocol):
    async def run(self): ...

    @property
    def score(self) -> int: ...

    @property
    def max_score(self) -> int: ...

    @property
    def report(self) -> str: ...

    @property
    def full_report(self) -> str: ...

    @property
    def model(self) -> Model: ...


class ModelValidator:
    _model: Model
    scenarios: list[ValidationScenario]
    _validation_scores: list[ScenarioScore] = []

    def __init__(self, model: Model, scenarios: list[ValidationScenario]):
        self._model = model
        self.scenarios = scenarios

    @property
    def score(self) -> int:
        score = 0
        for validation_score in self._validation_scores:
            score += validation_score.score
        return score

    @property
    def max_score(self) -> int:
        max_score = 0
        for validation_score in self._validation_scores:
            max_score += validation_score.max_score
        return max_score

    @property
    def report(self) -> str:
        report = f"For model {self.model.name} scored {self.score} points.\n"
        for validation_score in self._validation_scores:
            report += f"\tFor scenario {validation_score.scenario_id} scored {validation_score.score} points."
        return report

    @property
    def full_report(self) -> str:
        report = ""
        for validation_score in self._validation_scores:
            report += validation_score.report
        return report

    @property
    def model(self) -> Model:
        return self._model

    async def run(self):
        logger.info(f"Starting validation with model: {self.model.name}")

        for scenario in self.scenarios:
            logger.info(f"Validating scenario: {scenario.eval_scenario.id}")
            score = ScenarioScore(
                scenario_id=scenario.eval_scenario.id,
                mock_response_count=len(scenario.mock_responses),
                max_score=0,
                score=0,
                max_success=0,
                success=0,
                report=f"Scenario: {scenario.eval_scenario.id}",
            )
            for mock_response in scenario.mock_responses:
                logger.info(f"Validating mock response: {mock_response.description}")
                mock_response_score = 0
                mock_response_max_score = 0
                score.report += f"\tMock response: {mock_response.mock_response_content}"

                for expectatet_evaluation in mock_response.expected_evaluations:
                    logger.info(f"Validating expectation: {expectatet_evaluation.scenario_expectation_name}")
                    # First we need the actual expectation from the evaluation scenario.
                    # We can fetch it via its name, which we also store in the expectat evaluation.
                    expectation = get_expectation(scenario.eval_scenario, expectatet_evaluation)
                    if expectation is None:
                        raise ValueError(f"Expectation not found: {expectatet_evaluation.scenario_expectation_name}")

                    # We let the model decide if the mock response matches the expectations.
                    model_validation_response = self.model.invoke(
                        TEMPLATE.format(
                            statement=expectation.statement,
                            response=mock_response.mock_response_content,
                        )
                    )
                    actual_result = string_to_bool(model_validation_response)
                    expected_result = expectatet_evaluation.expected_evaluation

                    # Gathering scores.
                    score.max_success += 1
                    score.max_score += expectation.complexity
                    mock_response_max_score += expectation.complexity
                    if actual_result == expected_result:
                        score.success += 1
                        score.score += expectation.complexity
                        mock_response_score += expectation.complexity

                    # Report per expectation.
                    score.report += f"""
\t\texpectation: {colored(expectation.statement, 'yellow')}
\t\tactual result: {colored(model_validation_response, 'yellow')}
\t\texpected result: {colored(expected_result, 'yellow')}\n"""

                # Report per mock response.
                score_percent = round(mock_response_score / mock_response_max_score * 100, 2)
                score.report += f"\tScored {mock_response_score} of {mock_response_max_score} points ({score_percent}%) for mock response: {mock_response}"

            # Report per scenario.
            score_percent = round(
                score.score / score.max_score * 100,
                2,
            )
            score.report += f"Scored {score.score} of {score.max_score} point ({score_percent}%) for scenario {scenario.eval_scenario.id}"
            self._validation_scores.append(score)
