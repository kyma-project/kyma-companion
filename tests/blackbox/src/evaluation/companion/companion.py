import json
import time
from http import HTTPStatus
from logging import Logger

import requests
from common.config import Config
from common.metrics import Metrics
from pydantic import BaseModel


class ConversationPayload(BaseModel):
    query: str = ""
    resource_kind: str
    resource_api_version: str
    resource_name: str
    namespace: str


def get_headers(config: Config) -> dict:
    return {
        "Authorization": f"Bearer {config.companion_token}",
        "X-Cluster-Certificate-Authority-Data": config.test_cluster_ca_data,
        "X-Cluster-Url": config.test_cluster_url,
        "X-K8s-Authorization": config.test_cluster_auth_token,
        "Content-Type": "application/json",
    }


async def fetch_initial_questions(
    config: Config, payload: ConversationPayload, logger: Logger
) -> str:
    logger.debug(
        f"querying Companion: {config.companion_api_url} for initial questions..."
    )

    req_session = requests.Session()
    start_time = time.time()
    response = req_session.post(
        f"{config.companion_api_url}/api/conversations",
        json.dumps(payload.model_dump()),
        headers=get_headers(config),
    )
    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            f"failed to get response (status: {response.status_code}). "
            f"Response: {response.text}"
        )

    # record the response time.
    Metrics.get_instance().record_init_conversation_response_time(
        time.time() - start_time
    )

    return response


async def get_companion_response(
    config: Config, conversation_id: str, payload: ConversationPayload, logger: Logger
) -> str:
    logger.debug(
        f"querying Companion: {config.companion_api_url} for api-server: {config.test_cluster_url}"
    )

    headers = get_headers(config)
    headers["session-id"] = conversation_id

    uri = f"{config.companion_api_url}/api/conversations/{conversation_id}/messages"
    req_session = requests.Session()
    start_time = time.time()
    response = req_session.post(
        uri, json.dumps(payload.model_dump()), headers=headers, stream=True
    )
    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            f"failed to get response from the utils API (status: {response.status_code}). "
            f"Response: {response.text}"
        )

    # for line in response.iter_lines():
    #     # TODO: remove this and parse line to check if it is the AI response.
    #     return line

    # record the response time.
    Metrics.get_instance().record_conversation_response_time(time.time() - start_time)

    return payload.query
