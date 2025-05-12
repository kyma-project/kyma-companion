import time
from logging import Logger

from common.config import Config
from common.logger import get_logger
from common.output import print_header

from evaluation.companion.companion import (
    CompanionClient,
    ConversationPayload,
)
from evaluation.companion.response_models import (
    ConversationResponse,
    InitialQuestionsResponse,
)
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import Query, Scenario
from evaluation.validator.validator import IValidator


def process_scenario(scenario: Scenario, config: Config, validator: IValidator) -> None:
    """Process a scenario by getting the responses from the Companion API and validating the expectations."""
    logger = get_logger(scenario.id)
    print_header(f"Started processing of scenario: {scenario.id}")

    if len(scenario.queries) == 0:
        logger.info(f"skipping scenario {scenario.id} because no queries are defined.")
        return

    companion_client = CompanionClient(config)

    # get the initial questions and conversation id for the scenario.
    conversation_id = initialize_conversation(
        companion_client, config, logger, scenario
    )
    if not conversation_id:
        # If we fail to initialize the conversation,
        # the scenario is marked as failed and we can return.
        return

    # For each query in the scenario, we need to get the response from the Companion API.
    for query in scenario.queries:
        # Get Companion responses for the user query of the scenario.
        if not get_companion_responses(
            companion_client, config, logger, query, scenario, conversation_id
        ):
            # If we fail to get the response,
            # the scenario is marked as failed and we can return.
            return

        # Evaluate the query by the response from the Companion API against the expectations.
        if not evaluate_query(validator, config, logger, query, scenario):
            # If we fail to validate the scenario,
            # the scenario is marked as failed and we can return.
            return

    # Set the status to complete, if we made it through the whole test without issues.
    scenario.complete()

    logger.info("finished processing of scenario.")


def initialize_conversation(
    companion_client: CompanionClient,
    config: Config,
    logger: Logger,
    scenario: Scenario,
) -> str | None:
    """Before we can have further interactions with the Companion,
    we need to initialize the conversation with the Companion API.
    If this is successful we will return the received conversation_id which we can use
    for further interactions."""

    # Define payload for the Companion API.
    payload = ConversationPayload(
        resource_kind=scenario.queries[0].resource.kind,
        resource_api_version=scenario.queries[0].resource.api_version,
        resource_name=scenario.queries[0].resource.name,
        namespace=scenario.queries[0].resource.namespace,
    )

    # We retry the initialization multiple times to handle transient errors.
    retry_wait_time = config.retry_wait_time
    companion_error = None
    while retry_wait_time <= config.retry_max_wait_time:
        try:
            logger.debug("getting response from the initial conversations endpoint...")
            init_questions_response: InitialQuestionsResponse = (
                companion_client.fetch_initial_questions(payload, logger)
            )
            scenario.initial_questions = init_questions_response.initial_questions
            return init_questions_response.conversation_id

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
    companion_client: CompanionClient,
    config: Config,
    logger: Logger,
    query: Query,
    scenario: Scenario,
    conversation_id: str,
) -> bool:
    """After initializing the conversation, we get the responses from the Companion API for the user query.
    If this is successful we will return True, otherwise False."""

    payload = ConversationPayload(
        resource_kind=query.resource.kind,
        resource_api_version=query.resource.api_version,
        resource_name=query.resource.name,
        namespace=query.resource.namespace,
        query=query.user_query,
    )

    logger.debug(
        f"Getting response from companion for scenario: {scenario.id}, query: {query.user_query}"
    )

    # We retry multiple times to handle transient errors.
    retry_wait_time = config.retry_wait_time
    companion_error = None
    while retry_wait_time <= config.retry_max_wait_time:
        try:
            conversation_response: ConversationResponse = (
                companion_client.get_companion_response(
                    conversation_id, payload, logger
                )
            )
            query.actual_response = conversation_response.answer
            query.response_chunks = conversation_response.chunks
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
        query.test_status = TestStatus.FAILED
        query.test_status_reason = (
            f"failed to get response from the companion API. {companion_error}"
        )
        logger.error(
            f"skipping scenario {scenario.id} because failed to get response from the "
            f"companion API for scenario: {scenario.id}, query: {query.user_query}.\nError: {companion_error}"
        )
        # We return False to indicate that the scenario failed.
        return False

    # We return True to indicate that the scenario passed.
    return True


def evaluate_query(
    validator: IValidator,
    config: Config,
    logger: Logger,
    query: Query,
    scenario: Scenario,
) -> bool:
    """We evaluate the scenario's query by validating the expectations.
    If this is successful we will return True, otherwise False."""

    # We retry the validation multiple times to handle transient errors.
    retry_wait_time = config.retry_wait_time
    validation_error = None
    while retry_wait_time <= config.retry_max_wait_time:
        try:
            logger.debug(
                f"validating expectations for scenario: {scenario.id}, query: {query.user_query}"
            )
            query.evaluation_result = validator.get_deepeval_evaluate(query)
            break

        # If we get an exception, we log the error and retry after an increasing time
        # until we reach the maximum retry time.
        except Exception as e:
            validation_error = e
            logger.warning(
                f"failed to validate expectations "
                f"for scenario: {scenario.id}, query: {query.user_query}.\n Retrying in {retry_wait_time} "
                f"seconds. Error: {validation_error}"
            )
            time.sleep(retry_wait_time)
            retry_wait_time += config.retry_wait_time

    # If we run out of retries, we set the scenario status to failed.
    else:
        query.test_status = TestStatus.FAILED
        error_msg = (
            f"failed to validate expectations for "
            f"scenario: {scenario.id} after multiple retries, query: {query.user_query}.\n Error: {validation_error}"
        )
        logger.error(error_msg)
        query.test_status_reason += error_msg
        # We return False to indicate that the scenario failed.
        return False

    # We return True to indicate that the scenario passed.
    return True
