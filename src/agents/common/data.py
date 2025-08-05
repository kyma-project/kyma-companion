from pydantic import BaseModel

from agents.common.constants import CLUSTER
from services.k8s_resource_discovery import K8sResourceDiscovery, ResourceKind


class Message(BaseModel):
    """
    Message data model.
    Because of Pydantic version conflict between AICore and LangGraph, we keep this model as a duplicate of UserInput.
    """

    query: str
    resource_kind: str | None
    resource_api_version: str | None
    resource_name: str | None
    namespace: str | None
    resource_scope: str | None = None
    resource_related_to: str | None = None
    user_identifier: str | None = None

    def is_cluster_overview_query(self) -> bool:
        """Check if the query is an overview query."""
        return self.resource_kind.lower() == CLUSTER

    def add_details(self, resource_kind_details: ResourceKind) -> None:
        """Add details to the message."""
        self.resource_kind = resource_kind_details.kind
        self.resource_scope = resource_kind_details.get_scope()
        if self.resource_api_version and resource_kind_details.kind:
            self.resource_related_to = K8sResourceDiscovery.get_resource_related_to(
                self.resource_api_version, resource_kind_details.kind
            )
