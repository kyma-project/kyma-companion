import requests
from tests.blackbox.evaluation.src.utils.config import Config


def get_companion_response(config: Config, query: str) -> str:
    """Returns the response from the utils API."""

    headers = {
        "Authorization": f"Bearer {config.companion_token}",
        "X-Cluster-Certificate-Authority-Data": config.test_cluster_ca_data,
        "X-Cluster-Url": config.test_cluster_url,
        "X-K8s-Authorization": f"Bearer {config.test_cluster_auth_token}",
    }

    req_session = requests.Session()
    response = req_session.get(config.companion_api_url, headers=headers, stream=True)
    if response.status_code != 200:
        return ValueError(f"failed to get response from the utils API (status: {response.status_code}). "
                          f"Response: {response.text}")

    for line in response.iter_lines():
        print(line)
        break  # TODO: remove this and parse line to check if it is the AI response.