import asyncio
from logging import Logger

from tests.blackbox.evaluation.src.common.config import Config
from tests.blackbox.evaluation.src.common.output import print_test_results
from tests.blackbox.evaluation.src.companion.companion import get_companion_response
from tests.blackbox.evaluation.src.scenario.scenario import ScenarioList, Scenario
from tests.blackbox.evaluation.src.validator.evaluation import TestStatus
from tests.blackbox.evaluation.src.common.logger import get_logger
from tests.blackbox.evaluation.src.validator.utils import create_validator
from tests.blackbox.evaluation.src.validator.validator import ValidatorInterface


async def process_scenario(scenario: Scenario, config: Config, validator: ValidatorInterface, logger: Logger) -> None:
    # make a call to the Companion API and get response from Companion.
    try:
        logger.debug(f"Getting response from the companion API for scenario: {scenario.id}")
        response = await get_companion_response(config, scenario.description, logger)
        scenario.evaluation.actual_response = response
    except Exception as e:
        logger.debug(f"failed to get response from the companion API for scenario: {scenario.id}. Error: {e}")
        scenario.evaluation.status = TestStatus.FAILED
        scenario.evaluation.status_reason = f"failed to get response from the companion API. {e}"

    if scenario.evaluation.status == TestStatus.FAILED:
        logger.debug(f"skipping scenario {scenario.id} due to previous failure.")
        return

    # evaluate the expectations.
    logger.debug(f"evaluating expectations for scenario: {scenario.id}, "
                 f"actual_response: {scenario.evaluation.actual_response}")

    for expectation in scenario.expectations:
        try:
            result = validator.is_response_as_expected(expectation.statement, scenario.evaluation.actual_response)
            scenario.evaluation.add_expectation_result(expectation.name, expectation.complexity, result)
        except Exception as e:
            logger.debug(f"failed to validate expectation: {expectation.name} for scenario: {scenario.id}. Error: {e}")
            scenario.evaluation.status = TestStatus.FAILED
            scenario.evaluation.status_reason += f"failed to validate expectation {expectation.name}, {e}."

    # compute the overall results of test scenario.
    scenario.evaluation.evaluate()


async def main() -> None:
    # initialize the logger.
    logger = get_logger("main")

    # load the configuration.
    config = Config()
    config.init()

    # initialize the response validator.
    validator = create_validator(config)

    # load all the scenarios from the namespace scoped test data path.
    scenario_list = ScenarioList()
    scenario_list.load_all_namespace_scope_scenarios(config.namespace_scoped_test_data_path, logger)

    # process each scenario (with concurrency).
    tasks = []
    for scenario in scenario_list.items:
        tasks.append(process_scenario(scenario, config, validator, logger))
    # wait until all tasks are completed.
    await asyncio.gather(*tasks)

    # console out the results.
    # compute_score(scenario_list)
    print_test_results(scenario_list)


if __name__ == "__main__":
    asyncio.run(main())
