import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging import Logger

import github_action_utils as gha_utils
from common.config import Config
from common.logger import get_logger
from common.output import print_header, print_test_results
from evaluation.process_scenario import process_scenario
from evaluation.scenario.scenario import ScenarioList
from evaluation.validator.usage_data import TokenUsageDataValidator
from evaluation.validator.utils import create_validator
from evaluation.validator.validator import IValidator

SLEEP_INTERVAL = 2  # 2 seconds


def flush_logs(logger: Logger) -> None:
    """Flush all logs before printing test results."""
    for handler in logger.handlers:
        handler.flush()
    sys.stdout.flush()
    time.sleep(SLEEP_INTERVAL)


def main() -> None:
    """Main function to run the evaluation tests."""

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

    # flush all the logs.
    flush_logs(logger)

    print_header("Starting evaluation tests...")
    # process all scenarios.
    with gha_utils.group("Processing all scenarios"), ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            futures = [
                executor.submit(process_scenario, scenario, config, validator)
                for scenario in scenario_list.items
            ]

            # wait for all the threads to complete.
            for f in as_completed(futures):
                exp = f.exception()
                if exp is not None:
                    raise Exception(f"Failed to process scenario. Error: {exp}")

    # flush all the logs.
    flush_logs(logger)

    # validate that the token usage data is added to redis db.
    usage_tracker_validator = TokenUsageDataValidator(config.redis_url)
    token_usage_after_run = usage_tracker_validator.get_total_token_usage()
    total_usage = token_usage_after_run - token_usage_before_run
    if total_usage <= 0:
        logger.error("No token usage data found in redis db.")
        raise Exception("*** Tests failed: No token usage data found in redis db.")

    # compute the time taken by tests.
    time_taken = round((time.time() - start_time) / 60, 2)

    # print out the results.
    print_test_results(scenario_list, total_usage, time_taken)

    print_header(
        "NOTE: The evaluation tests will only be marked as failed if any of the critical expectations fail."
    )

    # flush all the logs.
    flush_logs(logger)

    # return the exit code based on the test results.
    if not scenario_list.is_test_passed():
        raise Exception("Tests failed.")


if __name__ == "__main__":
    main()
