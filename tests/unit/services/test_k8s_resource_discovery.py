from services.k8s_resource_discovery import K8sResourceDiscovery


class TestK8sResourceDiscovery:
    def test_initialize(self):
        K8sResourceDiscovery.initialize()

        assert len(K8sResourceDiscovery.api_resources) > 0
