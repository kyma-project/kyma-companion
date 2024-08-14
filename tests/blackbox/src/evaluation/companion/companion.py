from http import HTTPStatus
from logging import Logger

import requests
from common.config import Config


async def get_companion_response(config: Config, query: str, logger: Logger) -> str:
    headers = {
        "Authorization": f"Bearer {config.companion_token}",
        "X-Cluster-Certificate-Authority-Data": config.test_cluster_ca_data,
        "X-Cluster-Url": config.test_cluster_url,
        "X-K8s-Authorization": f"Bearer {config.test_cluster_auth_token}",
    }

    logger.debug(
        f"querying Companion: {config.companion_api_url} for api-server: {config.test_cluster_url}"
    )

    # TODO: add retry logic.
    req_session = requests.Session()
    response = req_session.get(config.companion_api_url, headers=headers, stream=True)
    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            f"failed to get response from the utils API (status: {response.status_code}). "
            f"Response: {response.text}"
        )

    # for line in response.iter_lines():
    #     # TODO: remove this and parse line to check if it is the AI response.
    #     return line

    return query
