import os

import pytest

from services.data_sanitizer import DataSanitizer
from services.k8s import K8sAuthHeaders, K8sClient


@pytest.fixture
def k8s_client() -> K8sClient:
    # Note: These tests uses the same cluster which is used in evaluation tests.
    # read Test cluster information from environment variables.
    # IMPORTANT: These tests use the token based authentication for the k8s cluster.

    api_server = os.environ.get("TEST_CLUSTER_URL", "")
    if api_server == "":
        raise ValueError("TEST_CLUSTER_URL: environment variable not set")

    user_token = os.environ.get("TEST_CLUSTER_AUTH_TOKEN", "")
    if user_token == "":
        raise ValueError("TEST_CLUSTER_AUTH_TOKEN: environment variable not set")

    certificate_authority_data = os.environ.get("TEST_CLUSTER_CA_DATA", "")
    if certificate_authority_data == "":
        raise ValueError("TEST_CLUSTER_CA_DATA: environment variable not set")

    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=api_server,
        x_cluster_certificate_authority_data=certificate_authority_data,
        x_k8s_authorization=user_token,
    )

    k8s_auth_headers.validate_headers()

    return K8sClient(
        k8s_auth_headers,
        data_sanitizer=DataSanitizer(),
    )


class TestK8sClient:
    @pytest.mark.parametrize(
        "uri",
        [
            # Test case: should be able to call node metrics endpoint.
            "apis/metrics.k8s.io/v1beta1/nodes",
        ],
    )
    def test_execute_get_api_request(self, k8s_client, uri):
        # when
        result = k8s_client.execute_get_api_request(uri)

        # then
        # the return type should be a list.
        assert isinstance(result, (dict | list))
        assert "kind" in result
        assert result["kind"] == "NodeMetricsList"

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
                "test-deployment-16",
            ),
            # Test case: should be able to list ReplicaSets in a specific namespace.
            (
                "apps/v1",
                "ReplicaSet",
                "kyma-system",
            ),
            # Test case: should be able to list Secrets in a specific namespace.
            (
                "v1",
                "Secret",
                "kyma-system",
            ),
            # Test case: should be able to list Eventing CRs in a specific namespace.
            (
                "operator.kyma-project.io/v1alpha1",
                "Eventing",
                "kyma-system",
            ),
            # Test case: should be able to list NATS CRs in a specific namespace.
            (
                "operator.kyma-project.io/v1alpha1",
                "NATS",
                "kyma-system",
            ),
            # Test case: should be able to list Function CRs in all namespaces.
            (
                "serverless.kyma-project.io/v1alpha2",
                "Function",
                "",
            ),
        ],
    )
    def test_list_resource(
        self, k8s_client, given_api_version, given_kind, given_namespace
    ):
        # when
        result = k8s_client.list_resources(
            api_version=given_api_version, kind=given_kind, namespace=given_namespace
        )

        # then
        # the return type should be a list.

        assert isinstance(result, list)
        # the list should not be empty.
        assert len(result) > 0
        # each item in the list should be a dictionary.
        for item in result:
            assert isinstance(item, dict)
            assert item["kind"] == given_kind
            assert item["apiVersion"] == given_api_version
            if item["kind"] == "Secret":
                assert item["data"] == {}

    @pytest.mark.parametrize(
        "given_api_version, given_kind, given_namespace, given_name",
        [
            # Test case: should be able to get a deployment.
            (
                "apps/v1",
                "Deployment",
                "kyma-system",
                "eventing-manager",
            ),
            # Test case: should be able to get Secret.
            (
                "v1",
                "Secret",
                "kyma-system",
                "eventing-nats-secret",
            ),
            # Test case: should be able to get Eventing CR.
            (
                "operator.kyma-project.io/v1alpha1",
                "Eventing",
                "kyma-system",
                "eventing",
            ),
            # Test case: should be able to get NATS CR.
            (
                "operator.kyma-project.io/v1alpha1",
                "NATS",
                "kyma-system",
                "eventing-nats",
            ),
            # Test case: should be able to get Function CR.
            (
                "serverless.kyma-project.io/v1alpha2",
                "Function",
                "test-function-8",
                "func1",
            ),
        ],
    )
    def test_get_resource(
        self, k8s_client, given_api_version, given_kind, given_namespace, given_name
    ):
        # when
        result = k8s_client.get_resource(
            api_version=given_api_version,
            kind=given_kind,
            namespace=given_namespace,
            name=given_name,
        )

        # then
        # the return type should be a dict.
        assert isinstance(result, dict)

        assert result["kind"] == given_kind
        assert result["apiVersion"] == given_api_version
        assert result["metadata"]["name"] == given_name
        assert result["metadata"]["namespace"] == given_namespace
        if result["kind"] == "Secret":
            assert result["data"] == {}

    @pytest.mark.parametrize(
        "given_api_version, given_kind, given_namespace, given_name",
        [
            # Test case: should be able to describe a pod.
            (
                "apps/v1",
                "Deployment",
                "test-deployment-16",
                "nginx",
            ),
            # Test case: should be able to describe Secret.
            (
                "v1",
                "Secret",
                "kyma-system",
                "eventing-nats-secret",
            ),
            # Test case: should be able to describe Eventing CR.
            (
                "operator.kyma-project.io/v1alpha1",
                "Eventing",
                "kyma-system",
                "eventing",
            ),
            # Test case: should be able to describe NATS CR.
            (
                "operator.kyma-project.io/v1alpha1",
                "NATS",
                "kyma-system",
                "eventing-nats",
            ),
            # Test case: should be able to describe Function CR.
            (
                "serverless.kyma-project.io/v1alpha2",
                "Function",
                "test-function-8",
                "func1",
            ),
        ],
    )
    def test_describe_resource(
        self, k8s_client, given_api_version, given_kind, given_namespace, given_name
    ):
        # when
        result = k8s_client.describe_resource(
            api_version=given_api_version,
            kind=given_kind,
            namespace=given_namespace,
            name=given_name,
        )

        # then
        # the return type should be a dict.
        assert isinstance(result, dict)

        assert result["kind"] == given_kind
        assert result["apiVersion"] == given_api_version
        assert result["metadata"]["name"] == given_name
        assert result["metadata"]["namespace"] == given_namespace
        if result["kind"] == "Secret":
            assert result["data"] == {}

        assert isinstance(result["events"], list)
        if len(result["events"]) > 0:
            for item in result["events"]:
                assert isinstance(item, dict)

    @pytest.mark.parametrize(
        "given_namespace",
        [
            # Test case: should be able to get list of not running pods.
            "test-deployment-16",
            # Test case: should be able to get list of not running pods in all namespaces.
            "",
        ],
    )
    def test_list_not_running_pods(self, k8s_client, given_namespace):
        # when
        result = k8s_client.list_not_running_pods(
            namespace=given_namespace,
        )

        # then
        # the return type should be a list.
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, dict)
            assert item["kind"] == "Pod"
            assert item["apiVersion"] == "v1"
            if given_namespace != "":
                assert item["metadata"]["namespace"] == given_namespace

    def test_list_nodes_metrics(
        self,
        k8s_client,
    ):
        # when
        result = k8s_client.list_nodes_metrics()

        # then
        # the return type should be a list.
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, dict)
            assert isinstance(item["usage"], dict)
            assert "cpu" in item["usage"]
            assert "memory" in item["usage"]
            assert item["usage"]["cpu"] != ""
            assert item["usage"]["memory"] != ""

    @pytest.mark.parametrize(
        "given_namespace",
        [
            # Test case: should be able to get events from all namespaces.
            "",
            # Test case: should be able to get events from a specific namespace.
            "test-horizontalpodautoscaler-17",
        ],
    )
    def test_list_k8s_events(self, k8s_client, given_namespace):
        # when
        result = k8s_client.list_k8s_events(namespace=given_namespace)

        # then
        # the return type should be a list.
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, dict)

    @pytest.mark.parametrize(
        "given_namespace",
        [
            # Test case: should be able to get events from all namespaces.
            "",
            # Test case: should be able to get events from a specific namespace.
            "test-horizontalpodautoscaler-17",
        ],
    )
    def test_list_k8s_warning_events(self, k8s_client, given_namespace):
        # when
        result = k8s_client.list_k8s_warning_events(namespace=given_namespace)

        # then
        # the return type should be a list.
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, dict)
            assert item["type"] == "Warning"

    @pytest.mark.parametrize(
        "given_kind,given_namespace,given_name",
        [
            # Test case: should be able to get events for specific resource.
            ("ReplicaSet", "test-horizontalpodautoscaler-17", "whoami-6c78674dc7"),
        ],
    )
    def test_list_k8s_events_for_resource(
        self, k8s_client, given_kind, given_namespace, given_name
    ):
        # when
        result = k8s_client.list_k8s_events_for_resource(
            kind=given_kind, namespace=given_namespace, name=given_name
        )

        # then
        # the return type should be a list.
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, dict)
            assert item["involvedObject"]["kind"] == given_kind
            assert item["involvedObject"]["name"] == given_name

    @pytest.mark.parametrize(
        "name,namespace,container_name,is_terminated,tail_limit",
        [
            # Test case: should be able to get logs of a running pod.
            (
                "eventing-manager-",
                "kyma-system",
                "manager",
                False,
                5,
            ),
        ],
    )
    def test_fetch_pod_logs(
        self, k8s_client, name, namespace, container_name, is_terminated, tail_limit
    ):
        # given
        # find complete pod name as pod names are dynamic.
        pods = k8s_client.list_resources(
            api_version="v1", kind="Pod", namespace=namespace
        )
        # find the first pod with name starting with given name.
        pod_name = next(
            (
                pod["metadata"]["name"]
                for pod in pods
                if pod["metadata"]["name"].startswith(name)
            ),
            None,
        )
        assert pod_name is not None

        # when
        result = k8s_client.fetch_pod_logs(
            pod_name, namespace, container_name, is_terminated, tail_limit
        )

        # then
        # the return type should be a list.
        assert isinstance(result, list)
        assert 0 < len(result) <= tail_limit
        for item in result:
            assert isinstance(item, str)
            assert item != ""
