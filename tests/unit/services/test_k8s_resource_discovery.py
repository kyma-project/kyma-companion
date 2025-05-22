import pytest

from services.k8s_resource_discovery import K8sResourceDiscovery


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
        assert (
            K8sResourceDiscovery.get_resource_related_to(group_version, kind)
            == expected_result
        )
