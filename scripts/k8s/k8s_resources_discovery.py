import json
from pathlib import Path

from kubernetes import client

from services.k8s import K8sAuthHeaders, K8sClient


def save_all_groups_with_resources(k8s_client: K8sClient, file_path: str) -> None:
    """
    Save all groups with resources to a json file.
    :param k8s_client:
    :return:
    """

    # Discover all API groups and versions
    discovery = client.ApisApi(k8s_client.api_client)
    api_response = discovery.get_api_versions()
    groups = api_response.to_dict()["groups"]
    for group in groups:
        for version in group["versions"]:
            print(f"Group: {group['name']}, Version: {version['version']}")
            res = k8s_client.get_group_version(version["group_version"])
            print("...")
            print(json.dumps(res, indent=4))
            version["resources"] = res.get("resources", [])

    with open(file_path, "w") as f:
        json.dump(groups, f, indent=4)


if __name__ == "__main__":
    # Validate if all the required K8s headers are provided.
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    result_file = Path(__file__).parent.parent / "config" / "api_resources.json"

    with config_path.open() as file:
        config_file = json.load(file)
        k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=config_file["TEST_CLUSTER_URL"],
            x_cluster_certificate_authority_data=config_file["TEST_CLUSTER_CA_DATA"],
            x_k8s_authorization=config_file["TEST_CLUSTER_AUTH_TOKEN"],
            x_client_certificate_data=config_file["TEST_CLUSTER_URL"],
            x_client_key_data=config_file["TEST_CLUSTER_URL"],
        )

    k8s_client = K8sClient(
        k8s_auth_headers=k8s_auth_headers,
        data_sanitizer=None,
    )

    save_all_groups_with_resources(k8s_client, result_file)
