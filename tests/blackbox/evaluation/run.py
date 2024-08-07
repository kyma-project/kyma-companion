import os
import yaml
import json
from typing import List
from langchain.prompts import PromptTemplate
from langchain.output_parsers.boolean import BooleanOutputParser
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI

from tests.blackbox.evaluation.src.utils.config import Config
from tests.blackbox.evaluation.src.utils.companion import get_companion_response
from tests.blackbox.evaluation.src.models.scenario import ScenarioList, Scenario
from tests.blackbox.evaluation.src.models.evaluation import TestStatus


TEMPLATE = PromptTemplate(
    template="""Please only answer with one word, YES or NO:
    Does the following statement apply for the following text? 
    The fact: 'The text {expectation}'. 
    The text: '{response}'""",
    input_variables=["expectation", "response"],
)


def create_llm_instance(config: Config) -> ChatOpenAI:
    model = ChatOpenAI(
        model_name="gpt4.o",
        temperature=0,
        deployment_id=config.aicore_deployment_id_gpt4,
        config_id=config.aicore_configuration_id_gpt4,
    )
    return model


def compute_score(scenario_list: ScenarioList) -> None:
    for scenario in scenario_list.items:
        print(f"Scenario: {scenario.id}")
        print(f"\tScenario status: {scenario.evaluation.status}")
        print(f"\tScenario mean_weighted_performance: {scenario.evaluation.compute_mean_weighted_performance()}")
        print(f"\tScenario standard_deviation: {scenario.evaluation.compute_standard_deviation()}")


def main() -> None:
    # Load the configuration.
    config = Config()
    config.init()

    # STAGE 1
    scenario_list = ScenarioList()

    # list out names of all directories in the specified path.
    test_scenario_dirs: List[str] = os.listdir(config.namespace_scoped_test_data_path)
    # loop over all the directory names
    for dir_name in test_scenario_dirs:
        scenario_file = config.namespace_scoped_test_data_path + "/" + dir_name + "/scenario.yaml"
        print(scenario_file)

        scenario_yaml = None
        try:
            with open(scenario_file, "r") as file:
                scenario_yaml = yaml.load(file, Loader=yaml.FullLoader)
        except Exception as e:
            raise Exception(f"Error reading scenario file: {scenario_file}", e)

        try:
            json_str = json.dumps(scenario_yaml)
            scenario = Scenario.model_validate_json(json_str)

            # add the scenario to the list.
            scenario_list.add(scenario)
        except Exception as e:
            raise Exception(f"Error parsing scenario file: {scenario_file}", e)

    print(f"Number of scenarios: {len(scenario_list.items)}")

    # STAGE 2
    # for each scenario in the list, make a call to the utils API.
    for scenario in scenario_list.items:
        print(f"Scenario: {scenario.id}")

        # make a call to the utils API.
        try:
            scenario.evaluation.actual_response = get_companion_response(config, scenario.description)
        except Exception as e:
            print(f"failed to get response from the companion API. {e}")
            scenario.evaluation.status = TestStatus.FAILED
            scenario.evaluation.status_reason = f"failed to get response from the companion API. {e}"
            continue

    # STAGE 3
    llm_model = create_llm_instance(config)
    boolean_parser = BooleanOutputParser()
    chain = TEMPLATE | llm_model | boolean_parser

    for scenario in scenario_list.items:
        print(f"Scenario: {scenario.id}")
        print(f"Scenario status: {scenario.evaluation.status}")
        print(f"Scenario actual_response: {scenario.evaluation.actual_response}")

        if scenario.evaluation.status == TestStatus.FAILED:
            print(f"skipping scenario {scenario.id} due to previous failure.")
            continue

        for expectation in scenario.expectations:
            result = chain.invoke({"expectation": expectation.statement,
                                     "response": scenario.evaluation.actual_response})

            print("Result:", result)

            scenario.evaluation.add_expectation_result(expectation.name, expectation.complexity, result)

        # compute the overall success of test scenario.
        scenario.evaluation.compute_status()

    # STAGE 4
    # Compute the scores.
    compute_score(scenario_list)


if __name__ == "__main__":
    main()
