from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.k8s import IK8sClient
from services.k8s_resource_discovery import K8sResourceDiscovery, ResourceKind


class TestResourceKind:
    @pytest.mark.parametrize(
        "description, is_namespaced, expected_result",
        [
            (
                "should return `namespaced` for namespaced resources",
                True,
                "namespaced",
            ),
            (
                "should return `cluster` for cluster scoped resources",
                False,
                "cluster",
            ),
        ],
    )
    def test_get_scope(self, description, is_namespaced, expected_result):
        resource = ResourceKind(
            name="test",
            singular_name="test",
            namespaced=is_namespaced,
            kind="test",
            verbs=["get"],
            categories=["test"],
            storage_version_hash="test",
        )
        assert resource.get_scope() == expected_result, description


class TestK8sResourceDiscovery:
    @pytest.mark.parametrize(
        "group_version, kind, expected_result",
        [
            (
                "core.kyma-project.io/v1beta1",
                "CustomConfig",
                "Kyma",
            ),
            (
                "cloud-resources.kyma-project.io/v1beta1",
                "CloudResources",
                "Kyma",
            ),
            (
                "eventing.kyma-project.io/v1alpha2",
                "Subscription",
                "Kyma",
            ),
            (
                "sme.sap.com/v1alpha1",
                "CAPApplication",
                "Kyma",
            ),
            (
                "keda.sh/v1alpha1",
                "TriggerAuthentication",
                "Kyma",
            ),
            (
                "dns.gardener.cloud/v1alpha1",
                "DNSEntry",
                "Kyma",
            ),
            (
                "telemetry.istio.io/v1",
                "Telemetry",
                "Kyma",
            ),
            (
                "destination.connectivity.api.sap/v1",
                "Destination",
                "Kyma",
            ),
            (
                "metrics.k8s.io/v1beta1",
                "NodeMetrics",
                "Kubernetes",
            ),
            (
                "apps/v1",
                "Deployment",
                "Kubernetes",
            ),
            (
                "v1",
                "Pod",
                "Kubernetes",
            ),
        ],
    )
    def test_get_resource_related_to(self, group_version, kind, expected_result):
        assert K8sResourceDiscovery.get_resource_related_to(group_version, kind) == expected_result

    def test_initialize(self):
        # Initialize the K8sResourceDiscovery class
        K8sResourceDiscovery.initialize()

        # Check if the resource relations are initialized correctly
        assert len(K8sResourceDiscovery.resource_relations) > 0
        assert len(K8sResourceDiscovery.api_resources) > 0

    @pytest.mark.parametrize(
        "description, resource_kind, resources, expected_name",
        [
            ("No match", "Pod", [], None),
            (
                "Single match",
                "Pod",
                [
                    ResourceKind(
                        name="pods",
                        singular_name="pod",
                        namespaced=True,
                        kind="Pod",
                        verbs=["get"],
                    )
                ],
                "pods",
            ),
            (
                "Multiple matches, one with matching singular_name",
                "Pod",
                [
                    ResourceKind(
                        name="pods",
                        singular_name="pod",
                        namespaced=True,
                        kind="Pod",
                        verbs=["get"],
                    ),
                    ResourceKind(
                        name="pods/status",
                        singular_name="",
                        namespaced=True,
                        kind="Pod",
                        verbs=["get"],
                    ),
                ],
                "pods",
            ),
            (
                "Multiple matches, none with matching singular_name, should return first",
                "Pod",
                [
                    ResourceKind(
                        name="pods",
                        singular_name="notpod",
                        namespaced=True,
                        kind="Pod",
                        verbs=["get"],
                    ),
                    ResourceKind(
                        name="pods/status",
                        singular_name="",
                        namespaced=True,
                        kind="Pod",
                        verbs=["get"],
                    ),
                ],
                "pods",
            ),
        ],
    )
    def test_find_resource_kind(self, description, resource_kind, resources, expected_name):
        k8s_client = Mock(spec=IK8sClient)
        discovery = K8sResourceDiscovery(k8s_client)
        result = discovery._find_resource_kind(resource_kind, resources)
        if expected_name is None:
            assert result is None, description
        else:
            assert result.name == expected_name, description

    @pytest.mark.parametrize(
        "description, group_version, kind, expected_name, expect_error",
        [
            (
                "Exact match in core/v1",
                "v1",
                "Pod",
                "pods",
                False,
            ),
            (
                "Match with group version",
                "apps/v1",
                "Deployment",
                "deployments",
                False,
            ),
            (
                "No match, should raise ValueError",
                "v1",
                "NonExistentKind",
                None,
                True,
            ),
            (
                "Kind with dot, should match base kind",
                "v1",
                "Pod.status",
                "pods",
                False,
            ),
            (
                "Match a Kyma resource",
                "eventing.kyma-project.io/v1alpha2",
                "Subscription",
                "subscriptions",
                False,
            ),
            (
                "Match a Kyma resource - Function",
                "serverless.kyma-project.io/v1alpha2",
                "Function",
                "functions",
                False,
            ),
        ],
    )
    def test_get_resource_kind_static(self, description, group_version, kind, expected_name, expect_error):
        # given
        k8s_client = Mock(spec=IK8sClient)
        discovery = K8sResourceDiscovery(k8s_client)

        # when / then
        if expect_error:
            with pytest.raises(ValueError):
                discovery.get_resource_kind_static(group_version, kind)
        else:
            result = discovery.get_resource_kind_static(group_version, kind)
            assert result.name == expected_name, description

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "description, group_version, kind, api_response, expected_name, expect_error",
        [
            (
                "Lookup for Pod should succeed",
                "v1",
                "Pod",
                {
                    "resources": [
                        {
                            "name": "pods",
                            "singular_name": "pod",
                            "namespaced": True,
                            "kind": "Pod",
                            "verbs": ["get"],
                        }
                    ]
                },
                "pods",
                False,
            ),
            (
                "Kind with dot should match base kind",
                "v1",
                "Pod.status",
                {
                    "resources": [
                        {
                            "name": "pods",
                            "singular_name": "pod",
                            "namespaced": True,
                            "kind": "Pod",
                            "verbs": ["get"],
                        }
                    ]
                },
                "pods",
                False,
            ),
            (
                "No matching kind should raise ValueError",
                "v1",
                "NonExistentKind",
                {
                    "resources": [
                        {
                            "name": "pods",
                            "singular_name": "pod",
                            "namespaced": True,
                            "kind": "Pod",
                            "verbs": ["get"],
                        }
                    ]
                },
                None,
                True,
            ),
            (
                "No group version found should raise ValueError",
                "apps/v1",
                "Deployment",
                None,
                None,
                True,
            ),
        ],
    )
    async def test_get_resource_kind_dynamic(
        self,
        description,
        group_version,
        kind,
        api_response,
        expected_name,
        expect_error,
    ):
        k8s_client = Mock()
        k8s_client.get_group_version = AsyncMock()
        k8s_client.get_group_version.return_value = api_response
        discovery = K8sResourceDiscovery(k8s_client)

        # when / then
        if expect_error:
            with pytest.raises(ValueError):
                await discovery.get_resource_kind_dynamic(group_version, kind)
        else:
            result = await discovery.get_resource_kind_dynamic(group_version, kind)
            assert result.name == expected_name, description

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "description, group_version, kind, static_result, dynamic_result, expect_error, expected_name",
        [
            (
                "Static lookup should succeed",
                "v1",
                "Pod",
                ResourceKind(
                    name="pods",
                    singular_name="pod",
                    namespaced=True,
                    kind="Pod",
                    verbs=["get"],
                ),
                None,
                False,
                "pods",
            ),
            (
                "Static lookup should fail, but dynamic lookup should succeed",
                "apps/v1",
                "Deployment",
                None,
                ResourceKind(
                    name="deployments",
                    singular_name="deployment",
                    namespaced=True,
                    kind="Deployment",
                    verbs=["get"],
                ),
                False,
                "deployments",
            ),
            (
                "Both static and dynamic lookup should fail",
                "v1",
                "NonExistentKind",
                None,
                None,
                True,
                None,
            ),
        ],
    )
    async def test_get_resource_kind(
        self,
        description,
        group_version,
        kind,
        static_result,
        dynamic_result,
        expect_error,
        expected_name,
    ):
        k8s_client = Mock()
        discovery = K8sResourceDiscovery(k8s_client)

        # Patch static and dynamic methods
        with (
            patch.object(discovery, "get_resource_kind_static") as mock_static,
            patch.object(discovery, "get_resource_kind_dynamic") as mock_dynamic,
        ):
            if static_result is not None:
                mock_static.return_value = static_result
            else:
                mock_static.side_effect = ValueError("Not found")
            if dynamic_result is not None:
                mock_dynamic.return_value = dynamic_result
            else:
                mock_dynamic.side_effect = ValueError("Not found")

            # when / then
            if expect_error:
                with pytest.raises(ValueError):
                    await discovery.get_resource_kind(group_version, kind)
            else:
                result = await discovery.get_resource_kind(group_version, kind)
                assert result.name == expected_name, description
