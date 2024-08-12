import logging
from typing import Protocol, List

from langchain.prompts import PromptTemplate
from termcolor import colored

from validation.utils.models import Model
from validation.utils.utils import string_to_bool
from validation.scenario_mock_responses import ScenarioMockResponses

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
    async def run(self):
        ...

    @property
    def score(self) -> float:
        ...

    @property
    def report(self) -> str:
        ...

    @property
    def full_report(self) -> str:
        ...

    @property
    def model(self) -> Model:
        ...


class ModelValidator:
    _model: Model
    data: List[ScenarioMockResponses]
    _score: float = 0
    _short_report: str = ""
    _report: str = ""

    def __init__(self, model: Model, data: List[ScenarioMockResponses]):
        self._model = model
        self.data = data

    @property
    def score(self) -> float:
        return self._score

    @property
    def report(self) -> str:
        return self._short_report

    @property
    def full_report(self) -> str:
        return self._report

    @property
    def model(self) -> Model:
        return self._model

    async def run(self):
        logging.info("Validating model: ", self.model.name)

        total_score = 0
        success_count = 0
        total_count = 0
        for scenario_mock_response in self.data:
            scenario_success_count = 0
            total_count += len(scenario_mock_response.expected_evaluations)
            scenario_report = ""
            for mock_response in scenario_mock_response.expected_evaluations:
                expectation = next((item for item in scenario_mock_response.scenario.expectations
                                    if item.name == mock_response.scenario_expectation_name), None)
                # actual evaluation response
                model_validation_response = self.model.invoke(
                    TEMPLATE.format(
                        statement=expectation.statement,
                        response=scenario_mock_response.mock_response_content,
                    )
                )
                actual_evaluation = string_to_bool(model_validation_response)
                expected_result = mock_response.expected_evaluation

                if actual_evaluation != expected_result:
                    total_score += expectation.complexity * 0
                else:
                    total_score += expectation.complexity * 1
                    success_count += 1
                    scenario_success_count += 1
                scenario_report += (
                    f"""
                    expectation: {colored(expectation.statement, 'yellow')}
                    actual result: {colored(model_validation_response, 'yellow')}
                    expected result: {colored(expected_result, 'yellow')}"""
                )

            success_rate = round(scenario_success_count / len(scenario_mock_response.expected_evaluations) * 100, 2)
            self._short_report += (f"scenario: {colored(scenario_mock_response.scenario_id, 'yellow')}\n"
                                   f"success rate: {colored(success_rate, 'yellow')}\n")

            self._report += (f"{self._short_report}\n"
                             f"expectation report: {colored(scenario_report, 'yellow')}\n"
                             )

        self._score = total_score
