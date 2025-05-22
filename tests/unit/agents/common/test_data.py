import pytest

from agents.common.data import Message
from services.k8s_resource_discovery import ResourceKind


class TestMessage:
    @pytest.mark.parametrize(
        "description, resource_kind, expected_result",
        [
            ("should return true when resource_kind is Cluster", "Cluster", True),
            (
                "should return true when resource_kind is cluster (lowercase)",
                "Cluster",
                True,
            ),
            ("should return false when resource_kind is not Cluster", "Pod", False),
        ],
    )
    def test_is_overview_query(self, description, resource_kind, expected_result):
        msg = Message(
            query="test",
            resource_kind=resource_kind,
            resource_name=None,
            resource_api_version=None,
            namespace=None,
            resource_scope=None,
            resource_related_to=None,
        )

        assert msg.is_overview_query() == expected_result, description

    @pytest.mark.parametrize(
        "description, initial, resource_kind_details, expected_kind, expected_scope, expected_related_to",
        [
            (
                "should update kind, scope, and related_to when api_version and kind are set",
                Message(
                    query="test",
                    resource_kind="DIFFERENT",
                    resource_api_version="v1",
                    resource_name=None,
                    namespace=None,
                    resource_scope=None,
                    resource_related_to=None,
                ),
                ResourceKind(
                    name="Pod",
                    singular_name="pod",
                    namespaced=True,
                    kind="Pod",
                    verbs=[],
                ),
                "Pod",
                "cluster",
                "Kubernetes",
            ),
            (
                "should update kind and scope, but not related_to if api_version is None",
                Message(
                    query="test",
                    resource_kind="DIFFERENT",
                    resource_api_version=None,
                    resource_name=None,
                    namespace=None,
                    resource_scope=None,
                    resource_related_to=None,
                ),
                ResourceKind(
                    name="Pod",
                    singular_name="pod",
                    namespaced=True,
                    kind="Pod",
                    verbs=["get"],
                ),
                "Pod",
                "cluster",
                None,
            ),
        ],
    )
    def test_add_details(
        self,
        description,
        initial,
        resource_kind_details,
        expected_kind,
        expected_scope,
        expected_related_to,
    ):
        initial.add_details(resource_kind_details)
        assert initial.resource_kind == expected_kind, description
        assert initial.resource_scope == expected_scope, description
        assert initial.resource_related_to == expected_related_to, description
