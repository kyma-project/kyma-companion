from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.prompts import PromptTemplate
from termcolor import colored
from src.models.validation.validation import Validation
from src.logic.utils import string_to_bool


TEMPLATE = PromptTemplate(
    template="""Please only answer with one word, true or false:
    Does the following statement apply for the following text? 
    The fact: 'The text {expectation}'. 
    The text: '{response}'""",
    input_variables=["expectation", "response"],
)


def validate(calibration: Validation, model: ChatOpenAI) -> None:
    """Calibrates a model using a calibration."""
    for mock_response in calibration.mock_responses.items:
        for wanted_result in mock_response.wanted_results.items:
            expectation = calibration.scenario.expectations.get_expectation(
                wanted_result.expectation_id
            )
            response = model.invoke(
                TEMPLATE.format(
                    expectation=expectation.statement,
                    response=mock_response.mock_response_content,
                )
            )
            mock_response.add_actual_result(
                wanted_result.expectation_id, string_to_bool(response.content)
            )
            print(
                f"""
    For mock response {colored(mock_response.mock_response_content, 'yellow')}
    with expectation {colored(expectation.statement, 'yellow')}
    got result: {colored(response.content, 'yellow')}
    wanted result: {colored(wanted_result.wanted_result, 'yellow')}"""
            )
