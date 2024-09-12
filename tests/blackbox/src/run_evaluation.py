import asyncio

from common.config import Config
from common.logger import get_logger
from common.output import print_test_results
from evaluation.process_scenario import process_scenario
from evaluation.scenario.scenario import ScenarioList
from evaluation.validator.utils import create_validator


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
        break
    # wait until all tasks are completed.
    await asyncio.gather(*tasks)

    # print out the results.
    print_test_results(scenario_list)

    # Pass or fail the tests.
    is_passed, reason = scenario_list.is_test_passed()
    if not is_passed:
        raise Exception(f"Tests failed: {reason}")


if __name__ == "__main__":
    asyncio.run(main())
