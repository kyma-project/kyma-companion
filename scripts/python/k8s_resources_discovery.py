### ************** K8s Resources Discovery **************
###
### This script is used to discover all the resources in the K8s cluster.
### It uses the K8s API to get the list of all resources and their versions.
### It saves the result to a json file: "kyma-companion/config/api_resources.json".
###
### HOW TO RUN THE SCRIPT?
### To run the script, you need to set the following environment variables:
### - SOURCE_CLUSTER_URL: The URL of the K8s cluster.
### - SOURCE_CLUSTER_CA_DATA: The CA data of the K8s cluster.
### - SOURCE_CLUSTER_AUTH_TOKEN: The auth token of the K8s cluster.
###
### Then run the script using the following command (terminal dir: kyma-companion/):
### poetry run python scripts/python/k8s_resources_discovery.py


import json
import os
import sys
from pathlib import Path

from kubernetes import client
from pydantic.json import pydantic_encoder

sys.path.append(os.path.join(os.path.dirname(__file__), "../../src"))
from services.k8s import K8sAuthHeaders, K8sClient
from services.k8s_resource_discovery import ApiResourceGroup


def save_all_groups_with_resources(k8s_client: K8sClient, file_path: Path) -> None:
    """
    Save all groups with resources to a json file.
    :param k8s_client:
    :param file_path: Path to the json file.
    :return:
    """

    # Get Core API group.
    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreApi.md
    # fetch the resources for the core API group.
    res = k8s_client.get_group_version("v1")
    # print(json.dumps(res, indent=4))

    core_api_group = {
        "api_version": None,
        "kind": None,
        "name": "core/v1",
        "server_address_by_client_cid_rs": None,
        "preferred_version": {"group_version": "core", "version": "v1"},
        "versions": [
            {
                "group_version": "core/v1",
                "version": "v1",
                "resources": res.get("resources", []),
            }
        ],
    }

    # Discover all other API groups and versions
    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/ApisApi.md
    print("Fetching CoreV1 Group...")
    discovery = client.ApisApi(k8s_client.api_client)
    api_response = discovery.get_api_versions()

    groups = api_response.to_dict()["groups"]
    for group in groups:
        for version in group["versions"]:
            print(f"Fetching Group: {group['name']}, Version: {version['version']}...")
            res = k8s_client.get_group_version(version["group_version"])
            # print(json.dumps(res, indent=4))
            version["resources"] = res.get("resources", [])

    # append core_api_group to start of groups list.
    groups.insert(0, core_api_group)

    # validate the data structure.
    api_resources: list[ApiResourceGroup] = [ApiResourceGroup.model_validate(g) for g in groups]

    with open(file_path, "w") as f:
        json.dump(api_resources, f, indent=4, default=pydantic_encoder)


if __name__ == "__main__":
    # Validate if all the required K8s headers are provided.
    config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
    result_file = Path(__file__).parent.parent.parent / "config" / "api_resources.json"

    # check required envs are set or not.
    if not os.getenv("SOURCE_CLUSTER_URL"):
        print("SOURCE_CLUSTER_URL env variable is not set.")
        sys.exit(1)
    if not os.getenv("SOURCE_CLUSTER_CA_DATA"):
        print("SOURCE_CLUSTER_CA_DATA env variable is not set.")
        sys.exit(1)
    if not os.getenv("SOURCE_CLUSTER_AUTH_TOKEN"):
        print("SOURCE_CLUSTER_AUTH_TOKEN env variable is not set.")
        sys.exit(1)

    print("Initializing K8s client...")
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=os.getenv("SOURCE_CLUSTER_URL"),
        x_cluster_certificate_authority_data=os.getenv("SOURCE_CLUSTER_CA_DATA"),
        x_k8s_authorization=os.getenv("SOURCE_CLUSTER_AUTH_TOKEN"),
    )

    k8s_client = K8sClient(
        k8s_auth_headers=k8s_auth_headers,
        data_sanitizer=None,
    )

    save_all_groups_with_resources(k8s_client, result_file)
    print(f"Saved all groups with resources to {result_file}")
