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
from evaluation.validator.validator import IValidator


def process_scenario(scenario: Scenario, config: Config, validator: IValidator) -> None:
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
        # If we fail to initialize the conversation,
        # the scenario is marked as failed and we can return.
        return

    # Get Companion responses for the user query of the scenario.
    if not get_companion_responses(
        companion_client, payload, config, logger, scenario, conversation_id
    ):
        # If we fail to get the response,
        # the scenario is marked as failed and we can return.
        return

    # Evaluate the scenario by the response from the Companion API against the expectations.
    if not evaluate_scenario(validator, config, logger, scenario):
        # If we fail to validate the scenario,
        # the scenario is marked as failed and we can return.
        return

    # Set the status to complete, if we made it through the whole test without issues.
    scenario.complete()

    logger.info("finished processing of scenario.")


def initialize_conversation(
    companion_client, payload, config, logger, scenario
) -> str | None:
    # Before we can have further interactions with the Companion,
    # we need to initialize the conversation with the Companion API.
    # If this is successful we will return the received conversation_id which we can use
    # for further interactions.

    # We retry the initialization multiple times to handle transient errors.
    retry_wait_time = config.retry_wait_time
    companion_error = None
    while retry_wait_time <= config.retry_max_wait_time:
        try:
            logger.debug("getting response from the initial conversations endpoint.")
            init_questions_response = companion_client.fetch_initial_questions(
                payload, logger
            )
            parsed_response = json.loads(init_questions_response.content)
            conversation_id = parsed_response[
                "conversation_id"
            ]
            scenario.initial_questions = parsed_response[
                "initial_questions"
            ]
            return str(conversation_id)

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
        scenario.test_status = TestStatus.FAILED
        scenario.test_status_reason = (
            "failed to call initialize conversation endpoint after multiple retries. "
            f"{companion_error}"
        )
        logger.error(
            f"skipping scenario because failed to call initialize conversation endpoint "
            f"after multiple retries. Error: {companion_error}"
        )
        # We return None to indicate that the initialization failed.
        return None


def get_companion_responses(
    companion_client, payload, config, logger, scenario, conversation_id
) -> bool:
    # After initializing the conversation, we get the responses from the Companion API for the user query.
    # If this is successful we will return True, otherwise False.

    payload.query = scenario.user_query
    logger.debug(f"Getting response from companion for scenario: {scenario.id}")

    # We retry multiple times to handle transient errors.
    retry_wait_time = config.retry_wait_time
    companion_error = None
    while retry_wait_time <= config.retry_max_wait_time:
        try:
            scenario.actual_response = companion_client.get_companion_response(
                conversation_id, payload, logger
            )
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
        scenario.test_status = TestStatus.FAILED
        scenario.test_status_reason = (
            f"failed to get response from the companion API. {companion_error}"
        )
        logger.error(
            f"skipping scenario {scenario.id} because failed to get response from the "
            f"companion API for scenario: {scenario.id}. Error: {companion_error}"
        )
        # We return False to indicate that the scenario failed.
        return False

    # We return True to indicate that the scenario passed.
    return True


def evaluate_scenario(validator, config, logger, scenario: Scenario) -> bool:
    # We evaluate the scenario by validating the expectations.
    # If this is successful we will return True, otherwise False.

    # We retry the validation multiple times to handle transient errors.
    retry_wait_time = config.retry_wait_time
    validation_error = None
    while retry_wait_time <= config.retry_max_wait_time:
        try:
            logger.debug(f"validating expectations for scenario: {scenario.id}")
            scenario.evaluation_result = validator.get_deepeval_evaluate(scenario)
            break

        # If we get an exception, we log the error and retry after an increasing time
        # until we reach the maximum retry time.
        except Exception as e:
            validation_error = e
            logger.warning(
                f"failed to validate expectations "
                f"for scenario: {scenario.id}. Retrying in {retry_wait_time} "
                f"seconds. Error: {validation_error}"
            )
            time.sleep(retry_wait_time)
            retry_wait_time += config.retry_wait_time

    # If we run out of retries, we set the scenario status to failed.
    else:
        scenario.test_status = TestStatus.FAILED
        error_msg = (
            f"failed to validate expectations "
            f"for scenario: {scenario.id} after multiple retries. Error: {validation_error}"
        )
        logger.error(error_msg)
        scenario.test_status_reason += (error_msg)
        # We return False to indicate that the scenario failed.
        return False

    # We return True to indicate that the scenario passed.
    return True
