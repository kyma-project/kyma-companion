import json
from logging import Logger

from common.config import Config

from evaluation.companion.companion import (
    ConversationPayload,
    fetch_initial_questions,
    get_companion_response,
)
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import Scenario
from evaluation.validator.validator import ValidatorInterface


async def process_scenario(
    scenario: Scenario, config: Config, validator: ValidatorInterface, logger: Logger
) -> None:
    payload = ConversationPayload(
        resource_kind=scenario.resource.kind,
        resource_api_version=scenario.resource.api_version,
        resource_name=scenario.resource.name,
        namespace=scenario.resource.namespace,
    )

    # first make a call to the Companion API to initialize the conversation.
    try:
        logger.debug(
            f"Getting response from the initial conversations endpoint for scenario: {scenario.id}"
        )
        init_questions_response = await fetch_initial_questions(config, payload, logger)
        conversation_id = json.loads(init_questions_response.content)["conversation_id"]
    except Exception as e:
        scenario.evaluation.status = TestStatus.FAILED
        scenario.evaluation.status_reason = (
            f"failed to call initialize conversation endpoint. {e}"
        )
        logger.error(
            f"skipping scenario {scenario.id} because failed to call initialize "
            f"conversation endpoint: {scenario.id}. Error: {e}"
        )
        # skip if the scenario has already failed.
        return

    # make a call to the Companion API and get response from Companion.
    try:
        logger.debug(
            f"Getting response from the companion API for scenario: {scenario.id}"
        )

        # set the query from the scenario.
        payload.query = scenario.user_query
        # get the response from the companion API multiple iterations to check idempotency.
        # i.e. we query the kyma companion multiple times with same question to check if the response is consistent.
        for _ in range(config.iterations):
            response = await get_companion_response(
                config, conversation_id, payload, logger
            )
            scenario.evaluation.add_actual_response(response)
    except Exception as e:
        scenario.evaluation.status = TestStatus.FAILED
        scenario.evaluation.status_reason = (
            f"failed to get response from the companion API. {e}"
        )
        logger.error(
            f"skipping scenario {scenario.id} because failed to get response from the "
            f"companion API for scenario: {scenario.id}. Error: {e}"
        )
        # skip if the scenario has already failed.
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
            # skip if the scenario has already failed.
            return

    # set the status to complete.
    scenario.complete()