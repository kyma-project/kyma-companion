import logging
from typing import Protocol, List

from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.prompts import PromptTemplate
from termcolor import colored

from validation.scenario_mock_responses import ScenarioMockResponses
from utils.utils import string_to_bool

TEMPLATE = PromptTemplate(
    template="""Please only answer with one word, true or false:
    Does the given statement apply for the given text?
    The statement: '{statement}'. 
    The text: '{response}'""",
    input_variables=["fact", "response"],
)


class Validator(Protocol):
    def run(self) -> float:
        ...


class ModelValidator:
    model: ChatOpenAI
    data: List[ScenarioMockResponses]

    def __init__(self, model: ChatOpenAI, data: List[ScenarioMockResponses]):
        self.model = model
        self.data = data

    def run(self) -> float:
        """Calibrates a model using a calibration."""

        logging.info("Validating model: ", self.model.name)

        results = {}
        total_score = 0
        for scenario_mock_response in self.data:
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

                actual_evaluation = string_to_bool(model_validation_response.content)
                expected_result = mock_response.expected_evaluation
                results[mock_response.scenario_expectation_name] = actual_evaluation

                if actual_evaluation != expected_result:
                    total_score += expectation.complexity.to_int() * 0
                else:
                    total_score += expectation.complexity.to_int() * 1

                print(
                    f"""
                    For mock response: {colored(scenario_mock_response.mock_response_content, 'yellow')}
                    with expectation: {colored(expectation.statement, 'yellow')}
                    got result: {colored(model_validation_response.content, 'yellow')}
                    wanted result: {colored(expected_result, 'yellow')}"""
                )
        return total_score
