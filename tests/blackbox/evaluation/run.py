import os
import yaml
import json
import requests
from typing import List
from langchain.prompts import PromptTemplate
# from langchain.chains import LLMChain

# from gen_ai_hub.proxy.langchain.init_models import init_llm

from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI

from tests.blackbox.evaluation.src.models.scenario import ScenarioList, Scenario
from tests.blackbox.evaluation.src.models.evaluation import TestStatus

EVALUATION_PATH = "/Users/I546341/git/kyma-project/kyma-companion/tests/blackbox/data/problems/namespace-scoped"
COMPANION_API_URL = os.environ.get("COMPANION_API_URL")
COMPANION_TOKEN = os.environ.get("COMPANION_TOKEN")
TEST_CLUSTER_URL = os.environ.get("TEST_CLUSTER_URL")
TEST_CLUSTER_CA_DATA = os.environ.get("TEST_CLUSTER_CA_DATA")
TEST_CLUSTER_AUTH_TOKEN = os.environ.get("TEST_CLUSTER_AUTH_TOKEN")
AICORE_DEPLOYMENT_ID_GPT4 = os.environ.get("AICORE_DEPLOYMENT_ID_GPT4")
AICORE_CONFIGURATION_ID_GPT4 = os.environ.get("AICORE_CONFIGURATION_ID_GPT4")

TEMPLATE = PromptTemplate(
    template="""Please only answer with one word, true or false:
    Does the following statement apply for the following text? 
    The fact: 'The text {expectation}'. 
    The text: '{response}'""",
    input_variables=["expectation", "response"],
)


def create_llm_instance() -> ChatOpenAI:
    model = ChatOpenAI(
        model_name="gpt4.o",
        temperature=0,
        deployment_id=AICORE_DEPLOYMENT_ID_GPT4,
        config_id=AICORE_CONFIGURATION_ID_GPT4,
    )
    return model


def compute_score(scenario_list: ScenarioList) -> None:
    pass


def main() -> None:
    # STAGE 1
    scenario_list = ScenarioList()

    # main_model_schema = Scenario.model_json_schema()
    #
    # print(json.dumps(main_model_schema, indent=2))

    # list out names of all directories in the specified path.
    test_scenario_dirs: List[str] = os.listdir(EVALUATION_PATH)
    # loop over all the directory names
    for dir_name in test_scenario_dirs:
        scenario_file = EVALUATION_PATH + "/" + dir_name + "/scenario.yaml"
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
    # for each scenario in the list, make a call to the companion API.
    print(f"API URL: {COMPANION_API_URL}")
    for scenario in scenario_list.items:
        print(f"Scenario: {scenario.id}")

        # make a call to the companion API.
        try:
            headers = {
                "Authorization": f"Bearer {COMPANION_TOKEN}",
                "X-Cluster-Certificate-Authority-Data": TEST_CLUSTER_CA_DATA,
                "X-Cluster-Url": TEST_CLUSTER_URL,
                "X-K8s-Authorization": f"Bearer {TEST_CLUSTER_AUTH_TOKEN}",
            }
            req_session = requests.Session()
            response = req_session.get(COMPANION_API_URL, headers=headers, stream=True)
            if response.status_code != 200:
                print(f"failed to get response from the companion API (status: {response.status_code}).")
                scenario.evaluation.status = TestStatus.FAILED
                scenario.evaluation.status_reason = \
                    f"failed to get response from the companion API (status: {response.status_code}). {response.text}"
                continue
        except Exception as e:
            print(f"failed to get response from the companion API. {e}")
            scenario.evaluation.status = TestStatus.FAILED
            scenario.evaluation.status_reason = f"failed to get response from the companion API. {e}"
            continue

        # print(f"Response: {response.text}")
        for line in response.iter_lines():
            scenario.evaluation.actual_response = line
            print(line)
            break  # TODO: remove this and parse line to check if it is the AI response.

    # STAGE 3
    llm_model = create_llm_instance()

    for scenario in scenario_list.items:
        print(f"Scenario: {scenario.id}")
        print(f"Scenario status: {scenario.evaluation.status}")
        print(f"Scenario actual_response: {scenario.evaluation.actual_response}")

        if scenario.evaluation.status == TestStatus.FAILED:
            print(f"skipping scenario {scenario.id} due to previous failure.")
            continue

        for expectation in scenario.expectations:
            template = TEMPLATE.invoke(expectation.statement, scenario.evaluation.actual_response)
            response = llm_model.invoke(template)
            print(response['text'])

            scenario.evaluation.add_expectation_result(expectation.name, response['text'] == 'true')

        # compute the overall success of test scenario.
        # scenario.evaluation.compute_status()

    # # Traverse the responses and evaluate the results using the evaluation model.
    # llm = init_llm('gpt-4', max_tokens=10000, top_p=1)
    # for scenario in scenario_list.items:
    #     print(f"Scenario: {scenario.id}")
    #     print(f"Scenario status: {scenario.evaluation.status}")
    #     print(f"Scenario actual_response: {scenario.evaluation.actual_response}")
    #
    #     if scenario.evaluation.status == TestStatus.FAILED:
    #         print(f"skipping scenario {scenario.id} due to previous failure.")
    #         continue
    #
    #     llm_chain = LLMChain(prompt=TEMPLATE, llm=llm)
    #     for expectation in scenario.expectations.items:
    #         response = llm_chain.invoke(expectation.statement, scenario.evaluation.actual_response)
    #         print(response['text'])
    #
    #         scenario.evaluation.add_expectation_result(expectation.name, response['text'] == 'true')
    #
    #     # compute the overall success of test scenario.
    #     # scenario.evaluation.compute_status()

    # # STAGE 4
    # # Compute the scores.
    # # compute_score(scenario_list)


if __name__ == "__main__":
    main()
