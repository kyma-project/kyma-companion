import asyncio
from logging import Logger

from dotenv import load_dotenv

from evaluation.companion.companion import get_companion_response
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import Scenario, ScenarioList
from evaluation.validator.utils import create_validator
from evaluation.validator.validator import ValidatorInterface
from common.config import Config
from common.logger import get_logger
from common.output import print_test_results


async def process_scenario(
        scenario: Scenario, config: Config, validator: ValidatorInterface, logger: Logger
) -> None:
    # make a call to the Companion API and get response from Companion.
    try:
        logger.debug(
            f"Getting response from the companion API for scenario: {scenario.id}"
        )
        # get the response from the companion API multiple iterations to check idempotency.
        for _ in range(config.iterations):
            response = await get_companion_response(
                config, scenario.description, logger
            )
            scenario.evaluation.add_actual_response(response)
    except Exception as e:
        logger.error(
            f"failed to get response from the companion API for scenario: {scenario.id}. Error: {e}"
        )
        scenario.evaluation.status = TestStatus.FAILED
        scenario.evaluation.status_reason = (
            f"failed to get response from the companion API. {e}"
        )

    # skip the evaluation if the scenario has already failed.
    if scenario.evaluation.status == TestStatus.FAILED:
        logger.warning(f"skipping scenario {scenario.id} due to previous failure.")
        return

    # evaluate the expectations.
    for expectation in scenario.expectations:
        try:
            # for each response, validate the expectation.
            for response in scenario.evaluation.actual_responses:
                result = validator.is_response_as_expected(
                    expectation.statement, response
                )
                expectation.add_result(result)
        except Exception as e:
            logger.error(
                f"failed to validate expectation: {expectation.name} for scenario: {scenario.id}. Error: {e}"
            )
            scenario.evaluation.status = TestStatus.FAILED
            scenario.evaluation.status_reason += (
                f"failed to validate expectation {expectation.name}, {e}."
            )

    # set the status to complete.
    scenario.complete()


async def main() -> None:
    # initialize the logger.
    logger = get_logger("main")

    # load the configuration.
    config = Config()

    # initialize the response validator.
    validator = create_validator(config)

    # load all the scenarios from the namespace scoped test data path.
    scenario_list = ScenarioList()
    scenario_list.load_all_namespace_scope_scenarios(
        config.namespace_scoped_test_data_path, logger
    )

    # process each scenario (with concurrency).
    tasks = []
    for scenario in scenario_list.items:
        tasks.append(process_scenario(scenario, config, validator, logger))
    # wait until all tasks are completed.
    await asyncio.gather(*tasks)

    # print out the results.
    print_test_results(scenario_list)


if __name__ == "__main__":
    asyncio.run(main())
