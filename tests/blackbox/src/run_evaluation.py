import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.config import Config
from common.logger import get_logger
from common.output import print_header, print_test_results, print_token_usage
from evaluation.process_scenario import process_scenario
from evaluation.scenario.scenario import ScenarioList
from evaluation.validator.usage_data import TokenUsageDataValidator
from evaluation.validator.utils import create_validator
from evaluation.validator.validator import IValidator


def main() -> None:
    # initialize the logger.
    logger = get_logger("main")
    start_time = time.time()

    # load the configuration.
    config = Config()

    # load all the scenarios from the namespace scoped test data path.
    scenario_list = ScenarioList()
    scenario_list.load_all_namespace_scope_scenarios(
        config.namespace_scoped_test_data_path, logger
    )

    # initialize the response validator.
    validator: IValidator = create_validator(config)
    usage_tracker_validator = TokenUsageDataValidator(config.redis_url)
    token_usage_before_run = usage_tracker_validator.get_total_token_usage()
    usage_tracker_validator.disconnect()

    # add each scenario to the executor.
    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        futures = [
            executor.submit(process_scenario, scenario, config, validator)
            for scenario in scenario_list.items
        ]

        # wait for all the threads to complete.
        for f in as_completed(futures):
            exp = f.exception()
            if exp is not None:
                raise Exception(f"Failed to process scenario. Error: {exp}")

    # # print out the results.
    # print_test_results(scenario_list)
    #
    # time_taken = round((time.time() - start_time) / 60, 2)
    # print(f"Total time taken by evaluation tests: {time_taken} minutes.")
    #
    # # validate that the token usage data is added to redis db.
    # usage_tracker_validator = TokenUsageDataValidator(config.redis_url)
    # token_usage_after_run = usage_tracker_validator.get_total_token_usage()
    # total_usage = token_usage_after_run - token_usage_before_run
    # if total_usage <= 0:
    #     logger.error("No token usage data found in redis db.")
    #     raise Exception("*** Tests failed: No token usage data found in redis db.")
    # print_token_usage(total_usage)
    #
    # if scenario_list.is_test_failed():
    #     print_header("Tests FAILED.")
    #     failed_scenarios = scenario_list.get_failed_scenarios()
    #     logger.error(
    #         f"Check the logs for tests with status: FAILED. Number of failed tests: {len(failed_scenarios)}"
    #     )
    #     raise Exception("Tests failed.")


if __name__ == "__main__":
    main()
