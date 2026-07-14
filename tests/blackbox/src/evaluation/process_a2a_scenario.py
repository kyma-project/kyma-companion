"""Scenario processing logic for the A2A Kyma agent evaluation.

Mirrors process_scenario.py but drives the A2A endpoint instead of the
plain conversation API.  The A2A client manages multi-turn state via
context_id; no separate "initialize conversation" step is needed.
"""

import time
from logging import Logger

from common.config import Config
from common.logger import get_logger
from common.output import print_detailed_query_results, print_header

from evaluation.companion.a2a_client import A2AClient, A2AEncryptionSession
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import Query, Scenario
from evaluation.validator.validator import IValidator


def process_a2a_scenario(scenario: Scenario, config: Config, validator: IValidator) -> None:
    """Process a scenario through the A2A Kyma agent endpoint.

    Creates one encryption session per scenario, then sends each query in
    sequence, passing the returned context_id forward so the agent sees the
    full conversation history.
    """
    logger = get_logger(scenario.id)
    print_header(f"Started processing of A2A scenario: {scenario.id}")

    if len(scenario.queries) == 0:
        logger.info(f"Skipping scenario {scenario.id}: no queries defined.")
        return

    try:
        encryption_session = A2AEncryptionSession.create(config)
    except Exception as exc:
        scenario.test_status = TestStatus.FAILED
        scenario.test_status_reason = f"Failed to create A2A encryption session: {exc}"
        logger.error(scenario.test_status_reason)
        return

    a2a_client = A2AClient(config, encryption_session)
    context_id: str | None = None

    for query in scenario.queries:
        if not _get_a2a_response(a2a_client, config, logger, query, scenario, context_id):
            scenario.test_status = TestStatus.FAILED
            scenario.test_status_reason = query.test_status_reason
            return

        # Carry the context_id forward for multi-turn conversations.
        # The client stores it in the query so we can retrieve it here.
        context_id = getattr(query, "_a2a_context_id", context_id)

        if not _evaluate_query(validator, config, logger, query, scenario):
            scenario.test_status = TestStatus.FAILED
            scenario.test_status_reason = query.test_status_reason
            return

        print_detailed_query_results(scenario, query)

    scenario.complete()
    logger.info("Finished processing A2A scenario.")


def _get_a2a_response(
    a2a_client: A2AClient,
    config: Config,
    logger: Logger,
    query: Query,
    scenario: Scenario,
    context_id: str | None,
) -> bool:
    """Call the A2A endpoint and store the answer on the query object.

    Retries with increasing back-off up to config.retry_max_wait_time.
    Returns True on success, False if all retries are exhausted.
    """
    retry_wait_time = config.retry_wait_time
    last_error = None

    while retry_wait_time <= config.retry_max_wait_time:
        try:
            logger.debug(f"Sending A2A query for scenario {scenario.id}: {query.user_query!r}")
            answer, new_context_id = a2a_client.send_message(
                query=query.user_query,
                resource_kind=query.resource.kind,
                resource_name=query.resource.name,
                resource_api_version=query.resource.api_version,
                namespace=query.resource.namespace,
                context_id=context_id,
            )
            query.actual_response = answer
            # Stash context_id so the caller can thread it forward.
            query._a2a_context_id = new_context_id  # type: ignore[attr-defined]
            return True

        except Exception as exc:
            last_error = exc
            logger.warning(
                f"A2A request failed for scenario {scenario.id}. Retrying in {retry_wait_time}s. Error: {exc}"
            )
            time.sleep(retry_wait_time)
            retry_wait_time += config.retry_wait_time

    query.test_status = TestStatus.FAILED
    query.test_status_reason = f"A2A request failed after multiple retries: {last_error}"
    logger.error(f"Skipping scenario {scenario.id}: A2A request exhausted retries. Error: {last_error}")
    return False


def _evaluate_query(
    validator: IValidator,
    config: Config,
    logger: Logger,
    query: Query,
    scenario: Scenario,
) -> bool:
    """Run deepeval against the query's expectations.

    Returns True on success, False if all retries are exhausted.
    """
    retry_wait_time = config.retry_wait_time
    last_error = None

    while retry_wait_time <= config.retry_max_wait_time:
        try:
            logger.debug(f"Evaluating A2A response for scenario {scenario.id}, query: {query.user_query!r}")
            query.evaluation_result = validator.get_deepeval_evaluate(query)
            return True

        except Exception as exc:
            last_error = exc
            logger.warning(
                f"Evaluation failed for scenario {scenario.id}. Retrying in {retry_wait_time}s. Error: {exc}"
            )
            time.sleep(retry_wait_time)
            retry_wait_time += config.retry_wait_time

    query.test_status = TestStatus.FAILED
    error_msg = (
        f"Evaluation exhausted retries for scenario {scenario.id}, query: {query.user_query!r}. Error: {last_error}"
    )
    query.test_status_reason += error_msg
    logger.error(error_msg)
    return False
