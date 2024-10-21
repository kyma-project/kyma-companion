import json
import time

from common.config import Config
from common.logger import get_logger

from evaluation.companion.companion import (
    CompanionClient,
    ConversationPayload,
)
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import Scenario
from evaluation.validator.validator import ValidatorInterface


def process_scenario(
    scenario: Scenario, config: Config, validator: ValidatorInterface
) -> None:
    logger = get_logger(scenario.id)
    logger.info("started processing of scenario.")

    # Initialize the Companion client.
    companion_client = CompanionClient(config)

    # Define payload for the Companion API.
    payload = ConversationPayload(
        resource_kind=scenario.resource.kind,
        resource_api_version=scenario.resource.api_version,
        resource_name=scenario.resource.name,
        namespace=scenario.resource.namespace,
    )

    # Initialize conversation.
    conversation_id = initialize_conversation(
        companion_client, payload, config, logger, scenario
    )
    if not conversation_id:
        return

    # Get Companion responses for the user query of the scenario.
    if not get_companion_responses(
        companion_client, payload, config, logger, scenario, conversation_id
    ):
        return

    # Evaluate the scenario by the response from the Companion API against the expectations.
    if not evaluate_scenario(validator, config, logger, scenario):
        return

    # Set the status to complete, if we made it through the whole test without issues.
    scenario.complete()


def initialize_conversation(companion_client, payload, config, logger, scenario):
    # Before we can have further interactions with the Companion,
    # we need to initialize the conversation with the Companion API.

    # We retry the initialization multiple times to handle transient errors.
    retry_wait_time = config.retry_wait_time
    while retry_wait_time <= config.retry_max_wait_time:
        companion_error = None
        try:
            logger.debug("getting response from the initial conversations endpoint.")
            init_questions_response = companion_client.fetch_initial_questions(
                payload, logger
            )
            conversation_id = json.loads(init_questions_response.content)[
                "conversation_id"
            ]
            return conversation_id

        # If we get an exception, we log the error and retry after an increasing time
        # until we reach the maximum retry time.
        except Exception as e:
            companion_error = e
            logger.warning(
                f"failed to call initialize conversation endpoint. "
                f"Retrying in {retry_wait_time} seconds. Error: {companion_error}"
            )
            time.sleep(retry_wait_time)
            retry_wait_time += config.retry_wait_time

    # If we run out of retries, we set the scenario status to failed.
    else:
        scenario.evaluation.status = TestStatus.FAILED
        scenario.evaluation.status_reason = (
            "failed to call initialize conversation endpoint after multiple retries. "
            f"{companion_error}"
        )
        logger.error(
            f"skipping scenario because failed to call initialize conversation endpoint "
            f"after multiple retries. Error: {companion_error}"
        )
        return None


def get_companion_responses(
    companion_client, payload, config, logger, scenario, conversation_id
):
    # After initializing the conversation, we get the responses from the Companion API for the user query.
    payload.query = scenario.user_query
    # We get the response multiple times to check if the response is consistent.
    # This is the so called idempotency check.
    for _ in range(config.iterations):
        logger.debug(f"Getting response from companion for scenario: {scenario.id}")

        # We retry the to querry multiple times to handle transient errors.
        retry_wait_time = config.retry_wait_time
        companion_error = None
        while retry_wait_time <= config.retry_max_wait_time:
            try:
                response = companion_client.get_companion_response(
                    conversation_id, payload, logger
                )
                # We store the response in the scenario evaluation,
                # so we can compare it with the expectations, later.
                scenario.evaluation.add_actual_response(response)
                break

            # If we get an exception, we log the error and retry after an increasing time
            # until we reach the maximum retry time.
            except Exception as e:
                companion_error = e
                logger.warning(
                    f"failed to get response from the companion API. "
                    f"Retrying in {retry_wait_time} seconds. Error: {companion_error}"
                )
                time.sleep(retry_wait_time)
                retry_wait_time += config.retry_wait_time

        # If we run out of retries, we set the scenario status to failed.
        else:
            scenario.evaluation.status = TestStatus.FAILED
            scenario.evaluation.status_reason = (
                f"failed to get response from the companion API. {companion_error}"
            )
            logger.error(
                f"skipping scenario {scenario.id} because failed to get response from the "
                f"companion API for scenario: {scenario.id}. Error: {companion_error}"
            )
            return False
    return True


def evaluate_scenario(validator, config, logger, scenario):
    # We evaluate the scenario by validating the expectations.
    for expectation in scenario.expectations:

        # We retry the validation multiple times to handle transient errors.
        retry_wait_time = config.retry_wait_time
        validation_error = None
        while retry_wait_time <= config.retry_max_wait_time:
            try:
                # For each response, validate the expectation.
                for response in scenario.evaluation.actual_responses:
                    result = validator.is_response_as_expected(
                        expectation.statement, response
                    )
                    expectation.add_result(result)
                break

            # If we get an exception, we log the error and retry after an increasing time
            # until we reach the maximum retry time.
            except Exception as e:
                validation_error = e
                logger.warning(
                    f"failed to validate expectation: {expectation.name} "
                    f"for scenario: {scenario.id}. Retrying in {retry_wait_time} "
                    f"seconds. Error: {validation_error}"
                )
                time.sleep(retry_wait_time)
                retry_wait_time += config.retry_wait_time

        # If we run out of retries, we set the scenario status to failed.
        else:
            logger.error(
                f"failed to validate expectation: {expectation.name} "
                f"for scenario: {scenario.id} after multiple retries. Error: {validation_error}"
            )
            scenario.evaluation.status = TestStatus.FAILED
            scenario.evaluation.status_reason += (
                f"failed to validate expectation {expectation.name} after multiple retries, "
                f"{validation_error}."
            )
            return False
    return True
