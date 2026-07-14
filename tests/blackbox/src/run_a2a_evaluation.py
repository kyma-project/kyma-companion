"""Entry point for the A2A Kyma agent evaluation tests.

Mirrors run_evaluation.py but drives the A2A endpoint
(POST /api/agent/kyma/chat) instead of the plain conversation API.

Usage:
    cd tests/blackbox
    poetry run python src/run_a2a_evaluation.py

The same config.json / environment variables used by run_evaluation.py
are used here (CONFIG_PATH, TEST_CLUSTER_URL, etc.).  Scenario YAML files
are loaded from the same data/test-cases/ directory.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging import Logger

import github_action_utils as gha_utils
from common.config import Config
from common.logger import get_logger
from common.output import print_header, print_test_results
from evaluation.process_a2a_scenario import process_a2a_scenario
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import Scenario, ScenarioList
from evaluation.validator.usage_data import TokenUsageDataValidator
from evaluation.validator.utils import create_validator
from evaluation.validator.validator import IValidator

SLEEP_INTERVAL = 2  # seconds


def process_a2a_scenario_with_retry(scenario: Scenario, config: Config, validator: IValidator) -> None:
    """Process an A2A scenario with retry logic for LLM non-determinism.

    Retries the whole scenario up to config.scenario_retries times on failure.
    Each retry creates a fresh A2A encryption session and starts a new
    conversation so there is no carry-over state between attempts.
    """
    logger = get_logger(f"{scenario.id}_a2a_retry")
    max_attempts = config.scenario_retries

    for attempt in range(1, max_attempts + 1):
        logger.info(f"A2A scenario {scenario.id} — attempt {attempt}/{max_attempts}")

        if attempt > 1:
            scenario.reset()

        scenario.attempt_number = attempt
        process_a2a_scenario(scenario, config, validator)
        scenario.record_attempt_history(attempt)

        if scenario.test_status != TestStatus.FAILED:
            if attempt > 1:
                logger.info(f"A2A scenario {scenario.id} passed on attempt {attempt}/{max_attempts}")
            break

        if attempt < max_attempts:
            logger.warning(
                f"A2A scenario {scenario.id} failed on attempt {attempt}/{max_attempts}. "
                f"Reason: {scenario.test_status_reason}. Retrying..."
            )
        else:
            logger.error(
                f"A2A scenario {scenario.id} failed after {max_attempts} attempts. "
                f"Final reason: {scenario.test_status_reason}"
            )


def flush_logs(logger: Logger) -> None:
    """Flush all log handlers before printing results."""
    for handler in logger.handlers:
        handler.flush()
    sys.stdout.flush()
    time.sleep(SLEEP_INTERVAL)


def main() -> None:
    """Run the A2A Kyma agent evaluation test suite."""
    logger = get_logger("a2a_main")
    start_time = time.time()

    config = Config()

    scenario_list = ScenarioList()
    scenario_list.load_all_namespace_scope_scenarios(config.namespace_scoped_test_data_path, logger)

    validator: IValidator = create_validator(config)
    usage_tracker_validator = TokenUsageDataValidator(config.redis_url)
    token_usage_before_run = usage_tracker_validator.get_total_token_usage()
    usage_tracker_validator.disconnect()

    flush_logs(logger)

    print_header("Starting A2A evaluation tests...")

    with (
        gha_utils.group("Processing all A2A scenarios"),
        ThreadPoolExecutor(max_workers=config.max_workers) as executor,
    ):
        futures = [
            executor.submit(process_a2a_scenario_with_retry, scenario, config, validator)
            for scenario in scenario_list.items
        ]

        for f in as_completed(futures):
            exc = f.exception()
            if exc is not None:
                raise Exception(f"Failed to process A2A scenario: {exc}")

    flush_logs(logger)

    usage_tracker_validator = TokenUsageDataValidator(config.redis_url)
    token_usage_after_run = usage_tracker_validator.get_total_token_usage()
    total_usage = token_usage_after_run - token_usage_before_run
    if total_usage <= 0:
        logger.error("No token usage data found in Redis after A2A evaluation run.")
        raise Exception("*** A2A tests failed: No token usage data found in Redis.")

    time_taken = round((time.time() - start_time) / 60, 2)
    print_test_results(scenario_list, total_usage, time_taken)

    print_header("NOTE: The A2A evaluation tests fail only when critical (required) expectations are not met.")

    flush_logs(logger)

    if not scenario_list.is_test_passed():
        raise Exception("A2A evaluation tests failed.")


if __name__ == "__main__":
    main()
