import json

from pydantic import BaseModel, Field

from services.k8s import IK8sClient
from utils import logging
from utils.settings import K8S_API_RESOURCES

GROUP_VERSION_SEPARATOR = "/"
GROUP_VERSION_PARTS_COUNT = 2


class ResourceKind(BaseModel):
    """ResourceKind is a class that represents a kind of resource in Kubernetes."""

    name: str
    singular_name: str = Field(alias="singularName")
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
    server_address_by_client_cid_rs: str | None
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
                K8sResourceDiscovery.api_resources = [ApiResourceGroup.model_validate(i) for i in items]

    def _split_group_version(self, group_version: str) -> tuple[str, str]:
        """
        Split the group_version string into group and version.
        :param group_version: The group/version string in the format <group>/<version>.
        :return: A tuple of (group, version).
        """
        if group_version == "":
            raise ValueError(
                "Invalid groupVersion: empty. Expected format: <group>/<version>."
            )
        # extract group and version from the group_version string '<group>/<version>'.
        group_version = group_version.strip().split(GROUP_VERSION_SEPARATOR)
        if len(group_version) != GROUP_VERSION_PARTS_COUNT:
            raise ValueError(
                f"Invalid groupVersion format: {group_version}. Expected format: <group>/<version>"
            )
        return group_version[0], group_version[1]

    def get_resource_kind_static(self, group_version: str, kind: str) -> ResourceKind:
        """
        Get the resource kind from the static API resources list loaded from JSON file.
        :param group_version:
        :param kind:
        :return:
        """
        group_name, version_name = self._split_group_version(group_version)

        # Check if the group exist in the API resources
        group = next(
            (g for g in K8sResourceDiscovery.api_resources if g.name == group_name),
            None,
        )
        if group is None:
            raise ValueError(f"Group '{group_name}' not found in API resources.")

        version = next((v for v in group.versions if v.version == version_name), None)
        if version is None:
            raise ValueError(
                f"Invalid groupVersion: {group_version}. "
                f"Version '{version_name}' not found in group '{group_name}'."
            )

        resource_kind = next(
            (r for r in version.resources if r.kind.lower() == kind.lower()), None
        )
        if resource_kind is None:
            raise ValueError(
                f"Invalid resource kind: {kind}. "
                f"Kind '{kind}' not found in groupVersion '{group_version}'."
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
        group_version = self.k8s_client.get_group_version(group_version)
        if group_version is None:
            raise ValueError(f"Invalid groupVersion: {group_version}. Not found.")

        resources: list[ResourceKind] = group_version.get("resources", [])
        resource_kind = next(
            (r for r in resources if r.kind.lower() == kind.lower()), None
        )
        if resource_kind is None:
            raise ValueError(
                f"Invalid resource kind: {kind}. "
                f"Kind '{kind}' not found in groupVersion '{group_version}'."
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
