"""Mock assistant for testing purposes; 
it is used to simulate the real assistant's behavior 
but lacks the actual logic and enhancements like RAG."""
from gen_ai_hub.proxy.langchain import ChatOpenAI
from termcolor import colored
from langchain.prompts import PromptTemplate
from src.models.evaluation.scenario import Scenario

TEMPLATE = PromptTemplate(
    template="""{problem}""",
    input_variables=["problem"],
)


def get_response_for_scenario(model: ChatOpenAI, scenario: Scenario) -> None:
    """For the scenario, tries to get an response from the model
    and stores it into the scenario's response field."""
    model_message = model.invoke(TEMPLATE.format(problem=scenario.problem))
    scenario.add_new_assistant_response(model_message)

    print(
        f"""
    For scenario {colored(scenario.scenario_id, 'yellow')}
    with problem {colored(scenario.problem, 'yellow')}
    got response: {colored(model_message.content, 'yellow')}
    """
    )
