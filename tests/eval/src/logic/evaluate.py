"""Evaluation module for the language model.
This module is responsible for evaluating the model's responses to the given scenarios.
"""
from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.prompts import PromptTemplate
from termcolor import colored

from src.logic.utils import string_to_bool
from src.models.evaluation.scenario import Scenario

TEMPLATE = PromptTemplate(
    template="""Please only answer with one word, true or false: Does the following statement apply for the following text? The statement: 'The text {statement}'. The text: '{response}'""",
    input_variables=["statement", "response"],
)


def evaluate_scenario(scenario: Scenario, model: ChatOpenAI) -> None:
    """Evaluate the scenario's assistant responses against the expectations via the model."""
    for response_id, response in scenario.assistant_responses:
        for expectation in scenario.expectations.items:
            model_message = model.invoke(
                TEMPLATE.format(statement=expectation.statement, response=response.content)
            )
            was_matched = string_to_bool(model_message.content)
            scenario.evaluation_results.add_new_evaluation_result(
                expectation_id=expectation.expectation_id,
                assistant_response_id=response_id,
                was_matched=was_matched,
            )

            print(
                f"""
            For scenario {colored(scenario.scenario_id, 'yellow')}
            with expectation {colored(expectation.statement, 'yellow')}
            and response {colored(response.content, 'yellow')}
            got result: {colored(was_matched, 'yellow')}
            """
            )