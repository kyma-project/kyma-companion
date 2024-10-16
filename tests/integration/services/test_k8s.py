import os
import pytest
from dotenv import load_dotenv

from services.k8s import K8sClient

# load env file if exists.
load_dotenv(os.getenv("ENV_FILE", "../../../.env.evaluation"))

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
        "given_api_version, given_kind, given_namespace",
        [
            # Test case: should be able to list deployments in all namespaces.
            (
                "apps/v1",
                "Deployment",
                "",
            ),
            # Test case: should be able to list pods in a specific namespace.
            (
                    "v1",
                    "Pod",
                    "nginx-wrong-image",
            ),
        ],
    )
    def test_list_resource(
        self, k8s_client, given_api_version, given_kind, given_namespace
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
        # the list should not be empty.
        assert len(result) > 0
        # each item in the list should be a dictionary.
        for item in result:
            assert type(item) == dict
            assert item["kind"] == given_kind
            assert item["apiVersion"] == given_api_version

    @pytest.mark.parametrize(
        "given_api_version, given_kind, given_namespace, given_name, expected_object",
        [
            # Test case: should be able to get a deployment.
            (
                    "apps/v1",
                    "Deployment",
                    "kyma-system",
                    "eventing-manager",
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
                    "apps/v1",
                    "Deployment",
                    "nginx-wrong-image",
                    "nginx",
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
        # assert len(result["events"]) > 0
        # for item in result["events"]:
        #     assert type(item) == dict

    @pytest.mark.parametrize(
        "given_namespace, expected_pod_names",
        [
            # Test case: should be able to get list of not running pods.
            (
                    "nginx-wrong-image",
                    ["nginx-"],
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
            # assert item["metadata"]["name"] in expected_pod_names

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
            "",
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

    @pytest.mark.parametrize(
        "given_namespace",
        [
            # Test case: should be able to get events from all namespaces.
            "",
        ],
    )
    def test_list_k8s_warning_events(
            self, k8s_client, given_namespace
    ):
        # when
        result = k8s_client.list_k8s_warning_events(namespace=given_namespace)

        # then
        # the return type should be a list.
        assert type(result) == list
        assert len(result) > 0
        for item in result:
            assert type(item) == dict
            assert item["type"] == "Warning"
