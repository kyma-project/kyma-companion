import os
import pytest
from dotenv import load_dotenv

from services.k8s import K8sClient

if not load_dotenv("../../../.env.evaluation"):
    raise ValueError("failed to load .env.evaluation")

@pytest.fixture
def k8s_client() -> K8sClient:
    # Note: These tests uses the same cluster which is used in evaluation tests.
    # read Test cluster information from environment variables.
    api_server = os.environ.get('TEST_CLUSTER_URL', '')
    if api_server == '':
        raise ValueError("TEST_CLUSTER_URL: environment variable not set")

    user_token = os.environ.get('TEST_CLUSTER_AUTH_TOKEN', '')
    if user_token == '':
        raise ValueError("TEST_CLUSTER_AUTH_TOKEN: environment variable not set")

    certificate_authority_data = os.environ.get('TEST_CLUSTER_CA_DATA', '')
    if certificate_authority_data == '':
        raise ValueError("TEST_CLUSTER_CA_DATA: environment variable not set")

    return K8sClient(api_server, user_token, certificate_authority_data)


class TestK8sClient:
    @pytest.mark.parametrize(
        "given_api_version, given_kind, given_namespace, expected_objects_names",
        [
            # Test case: should be able to list pods in all namespaces.
            (
                "v1",
                "Pod",
                "",
                None,
            ),
            # Test case: should be able to list pods in a specific namespace.
            (
                    "v1",
                    "Pod",
                    "companion-integration-tests-1",
                    ["failingpod"],
            ),
        ],
    )
    def test_list_resource(
        self, k8s_client, given_api_version, given_kind, given_namespace, expected_objects_names
    ):
        # when
        result = k8s_client.list_resources(
            api_version=given_api_version,
            kind=given_kind,
            namespace=given_namespace
        )

        # then
        # the return type should be a list.
        assert type(result) == list
        # the length of the list should be greater than 0.
        if given_namespace == "":
            assert len(result) > 0
        else:
            assert len(result) == len(expected_objects_names)
        # each item in the list should be a dictionary.
        for item in result:
            assert type(item) == dict
            assert item["kind"] == given_kind
            assert item["apiVersion"] == given_api_version
            if expected_objects_names  is not None:
                assert item["metadata"]["name"] in expected_objects_names

    @pytest.mark.parametrize(
        "given_api_version, given_kind, given_namespace, given_name, expected_object",
        [
            # Test case: should be able to get a pod.
            (
                    "v1",
                    "Pod",
                    "companion-integration-tests-1",
                    "failingpod",
                    None,
            ),
        ],
    )
    def test_get_resource(
            self, k8s_client, given_api_version, given_kind, given_namespace, given_name, expected_object
    ):
        # when
        result = k8s_client.get_resource(
            api_version=given_api_version,
            kind=given_kind,
            namespace=given_namespace,
            name=given_name
        )

        # then
        # the return type should be a dict.
        assert type(result) == dict

        assert result["kind"] == given_kind
        assert result["apiVersion"] == given_api_version
        assert result["metadata"]["name"] == given_name
        assert result["metadata"]["namespace"] == given_namespace

    @pytest.mark.parametrize(
        "given_api_version, given_kind, given_namespace, given_name, expected_object",
        [
            # Test case: should be able to get a pod.
            (
                    "v1",
                    "Pod",
                    "companion-integration-tests-1",
                    "failingpod",
                    None,
            ),
        ],
    )
    def test_describe_resource(
            self, k8s_client, given_api_version, given_kind, given_namespace, given_name, expected_object
    ):
        # when
        result = k8s_client.describe_resource(
            api_version=given_api_version,
            kind=given_kind,
            namespace=given_namespace,
            name=given_name
        )

        # then
        # the return type should be a dict.
        assert type(result) == dict

        assert result["kind"] == given_kind
        assert result["apiVersion"] == given_api_version
        assert result["metadata"]["name"] == given_name
        assert result["metadata"]["namespace"] == given_namespace

        assert type(result["events"]) == list
        assert len(result["events"]) > 0
        for item in result["events"]:
            assert type(item) == dict

    @pytest.mark.parametrize(
        "given_namespace, expected_pod_names",
        [
            # Test case: should be able to get list of not running pods.
            (
                    "companion-integration-tests-1",
                    ["failingpod"],
            ),
        ],
    )
    def test_list_not_running_pods(
            self, k8s_client, given_namespace, expected_pod_names
    ):
        # when
        result = k8s_client.list_not_running_pods(
            namespace=given_namespace,
        )

        # then
        # the return type should be a list.
        assert type(result) == list
        assert len(result) == len(expected_pod_names)
        for item in result:
            assert type(item) == dict
            assert item["kind"] == "Pod"
            assert item["apiVersion"] == "v1"
            assert item["metadata"]["namespace"] == given_namespace
            assert item["metadata"]["name"] in expected_pod_names

    def test_list_nodes_metrics(
            self, k8s_client,
    ):
        # when
        result = k8s_client.list_nodes_metrics()

        # then
        # the return type should be a list.
        assert type(result) == list
        assert len(result) > 0
        for item in result:
            assert type(item) == dict
            assert type(item["usage"]) == dict
            assert "cpu" in item["usage"]
            assert "memory" in item["usage"]
            assert type(item["usage"]["cpu"]) != ""
            assert type(item["usage"]["memory"]) != ""

    @pytest.mark.parametrize(
        "given_namespace",
        [
            # Test case: should be able to get events from all namespaces.
            (
                    "",
            ),
        ],
    )
    def test_list_k8s_events(
            self, k8s_client, given_namespace
    ):
        # when
        result = k8s_client.list_k8s_events(namespace=given_namespace)

        # then
        # the return type should be a list.
        assert type(result) == list
        assert len(result) > 0
        for item in result:
            assert type(item) == dict
