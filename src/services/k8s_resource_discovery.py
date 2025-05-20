import json

from pydantic import BaseModel, Field

from services.k8s import IK8sClient
from utils import logging
from utils.settings import K8S_API_RESOURCES


class ResourceKind(BaseModel):
    """ResourceKind is a class that represents a kind of resource in Kubernetes."""

    name: str
    singular_name: str | None = Field(alias="singularName", default=None)
    namespaced: bool
    kind: str
    verbs: list[str]
    categories: list[str] | None = None
    storage_version_hash: str | None = Field(alias="storageVersionHash", default=None)


class Version(BaseModel):
    """Version is a class that represents a version of an API resource."""

    group_version: str
    version: str
    resources: list[ResourceKind]


class PreferredVersion(BaseModel):
    """PreferredVersion is a class that represents the preferred version of an API resource."""

    group_version: str
    version: str


class ApiResourceGroup(BaseModel):
    """ApiResourceGroup is a class that represents a group of API resources in Kubernetes."""

    api_version: str | None
    kind: str | None
    name: str
    preferred_version: PreferredVersion
    server_address_by_client_cid_rs: str | list | None
    versions: list[Version]


class K8sResourceDiscovery:
    """
    K8sResourceDiscovery is a class that provides methods to discover Kubernetes resources.
    """

    # Class static variable to store API resources
    api_resources: list[ApiResourceGroup] = []

    def __init__(self, k8s_client: IK8sClient):
        self.k8s_client = k8s_client
        self.logger = logging.get_logger(self.__class__.__name__)

        # read the json file ./config/api_resources.json
        # and store the data in self.api_resources
        if len(K8sResourceDiscovery.api_resources) == 0:
            self.logger.info(f"Loading API resources from file: {K8S_API_RESOURCES}")
            with open(K8S_API_RESOURCES) as f:
                items = json.load(f)
                K8sResourceDiscovery.api_resources = [
                    ApiResourceGroup.model_validate(i) for i in items
                ]

    def get_resource_kind_static(self, group_version: str, kind: str) -> ResourceKind:
        """
        Get the resource kind from the static API resources list loaded from JSON file.
        :param group_version:
        :param kind:
        :return:
        """
        group_version_local = (
            "core/v1" if group_version.lower() == "v1" else group_version.lower()
        )
        kind_local = kind.split(".")[0] if "." in kind else kind

        # Check if the group version exists in the resources.
        self.logger.debug(
            f"looking for Kind {kind_local}: {group_version_local} in local api resources list..."
        )
        resource_kind: ResourceKind | None = None
        for group in K8sResourceDiscovery.api_resources:
            for version in group.versions:
                if version.group_version == group_version_local:
                    # Check if the kind exists in the resources of the version
                    resource_kind = next(
                        (
                            r
                            for r in version.resources
                            if r.kind.lower() == kind_local.lower()
                        ),
                        None,
                    )
                    if resource_kind is not None:
                        break

        if resource_kind is None:
            raise ValueError(
                f"Invalid resource kind: {kind}. "
                f"Kind '{kind}' (Actual search: {kind_local}) not found in groupVersion '{group_version}'."
            )
        return resource_kind

    def get_resource_kind_dynamic(self, group_version: str, kind: str) -> ResourceKind:
        """
        Get the resource kind from the K8s API resources list.
        This is a dynamic lookup that queries the K8s API for the resource kind.
        :param group_version:
        :param kind:
        :return:
        """
        group_version_details = self.k8s_client.get_group_version(group_version)
        if group_version_details is None:
            raise ValueError(f"Invalid groupVersion: {group_version}. Not found.")

        resources: list[ResourceKind] = [
            ResourceKind.model_validate(i)
            for i in group_version_details.get("resources", [])
        ]
        kind_local = kind.split(".")[0] if "." in kind else kind
        resource_kind = next(
            (r for r in resources if r.kind.lower() == kind_local.lower()), None
        )
        if resource_kind is None:
            raise ValueError(
                f"Invalid resource kind: {kind}. "
                f"Kind '{kind}' (Actual search: {kind_local}) not found in groupVersion '{group_version}'."
            )
        return resource_kind

    def get_resource_kind(self, group_version: str, kind: str) -> ResourceKind:
        """
        Get the resource kind by first trying static lookup and then dynamic lookup.
        :param group_version:
        :param kind:
        :return:
        """
        try:
            # First try static lookup.
            return self.get_resource_kind_static(group_version, kind)
        except ValueError as e:
            self.logger.warning(
                f"Error while getting resource statically "
                f"(group_version: {group_version}, kind: {kind}): {e}\n "
                f"Looking up dynamically..."
            )
            # If static lookup fails, try dynamic lookup.
            return self.get_resource_kind_dynamic(group_version, kind)
        except Exception as e:
            self.logger.error(
                f"Error while getting resource (group_version: {group_version}, kind: {kind}): {e}"
            )
            raise
