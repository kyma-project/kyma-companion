import json
import re

from pydantic import AliasChoices, BaseModel, Field
from tenacity import retry, stop_after_attempt

from services.k8s import IK8sClient
from utils import logging
from utils.logging import after_log
from utils.settings import K8S_API_RESOURCES_JSON_FILE, K8S_RESOURCE_RELATIONS_JSON_FILE

logger = logging.get_logger(__name__)

RETRY_ATTEMPTS = 3


class ResourceKind(BaseModel):
    """ResourceKind is a class that represents a kind of resource in Kubernetes."""

    name: str
    singular_name: str | None = Field(
        validation_alias=AliasChoices("singular_name", "singularName"), default=None
    )
    namespaced: bool  # defines if it is namespaced or cluster scoped resource
    kind: str
    verbs: list[str]
    categories: list[str] | None = None
    storage_version_hash: str | None = Field(
        validation_alias=AliasChoices("storage_version_hash", "storageVersionHash"),
        default=None,
    )

    def get_scope(self) -> str:
        """Get the scope of the resource kind."""
        return "cluster" if self.namespaced else "namespaced"


class Version(BaseModel):
    """Version is a class that represents a version of an API resource."""

    group_version: str = Field(
        validation_alias=AliasChoices("group_version", "groupVersion")
    )
    version: str
    resources: list[ResourceKind]


class PreferredVersion(BaseModel):
    """PreferredVersion is a class that represents the preferred version of an API resource."""

    group_version: str = Field(
        validation_alias=AliasChoices("group_version", "groupVersion")
    )
    version: str


class ApiResourceGroup(BaseModel):
    """ApiResourceGroup is a class that represents a group of API resources in Kubernetes."""

    api_version: str | None = Field(
        validation_alias=AliasChoices("api_version", "apiVersion")
    )
    kind: str | None
    name: str
    preferred_version: PreferredVersion = Field(
        validation_alias=AliasChoices("preferred_version", "preferredVersion")
    )
    server_address_by_client_cid_rs: str | list | None
    versions: list[Version]


class K8sResourceRelation(BaseModel):
    """K8sResourceRelation is a class that represents the relation of a resource to modules."""

    kind_pattern: str = Field(alias="kindPattern")
    group_version_pattern: str = Field(alias="groupVersionPattern")
    related_to: str = Field(alias="relatedTo")


class K8sResourceDiscovery:
    """
    K8sResourceDiscovery is a class that provides methods to discover Kubernetes resources.
    """

    # Class static variable to store API resources
    api_resources: list[ApiResourceGroup] = []
    resource_relations: list[K8sResourceRelation] = []

    def __init__(self, k8s_client: IK8sClient):
        K8sResourceDiscovery.initialize()
        self.k8s_client = k8s_client

    @staticmethod
    def initialize() -> None:
        """Static method to initialize the K8sResourceDiscovery class."""
        # load the json file ./config/api_resources.json.
        if len(K8sResourceDiscovery.api_resources) == 0:
            logger.info(
                f"Loading API resources from file: {K8S_API_RESOURCES_JSON_FILE}"
            )
            with open(K8S_API_RESOURCES_JSON_FILE) as f:
                items = json.load(f)
                K8sResourceDiscovery.api_resources = [
                    ApiResourceGroup.model_validate(i) for i in items
                ]

        # load the json file ./config/kyma_resource_patterns.json.
        if len(K8sResourceDiscovery.resource_relations) == 0:
            logger.info(
                f"Loading resource relations from file: {K8S_RESOURCE_RELATIONS_JSON_FILE}"
            )
            with open(K8S_RESOURCE_RELATIONS_JSON_FILE) as f:
                items = json.load(f)
                K8sResourceDiscovery.resource_relations = [
                    K8sResourceRelation.model_validate(i) for i in items
                ]

    @staticmethod
    def get_resource_related_to(group_version: str, kind: str) -> str:
        """
        Get the related module of a resource based on its group version and kind.
        :param group_version:
        :param kind:
        :return:
        """
        K8sResourceDiscovery.initialize()
        for relation in K8sResourceDiscovery.resource_relations:
            if re.fullmatch(
                relation.group_version_pattern, group_version.lower()
            ) and re.fullmatch(relation.kind_pattern, kind):
                return relation.related_to
        return "Kubernetes"  # Default to Kubernetes if no match found

    def _find_resource_kind(
        self, resource_kind: str, resources: list[ResourceKind]
    ) -> ResourceKind | None:
        """
        Find the resource kind in the list of resources.
        :param resource_kind:
        :param resources:
        :return:
        """
        # there may be multiple resources with the same kind but different names.
        filtered = [r for r in resources if r.kind.lower() == resource_kind.lower()]
        if len(filtered) == 0:
            return None
        if len(filtered) == 1:
            return filtered[0]
        # if there are multiple resources with the same kind, try to find one with same singular_name and kind.
        resource = next(
            (
                r
                for r in filtered
                if r.singular_name and r.singular_name.lower() == r.kind.lower()
            ),
            None,
        )
        if resource is not None:
            return resource

        # if there are still multiple resources with the same kind, return the first one.
        names = [r.name for r in filtered]
        logger.warning(
            f"Multiple resources found with kind {resource_kind}: {names}. "
            f"Returning the first one."
        )
        return filtered[0]

    def get_resource_kind_static(self, group_version: str, kind: str) -> ResourceKind:
        """
        Get the resource kind from the static API resources list loaded from JSON file.
        The JSON file was generated by running the script: `kyma-companion/scripts/python/k8s_resources_discovery.py`.
        :param group_version:
        :param kind:
        :return:
        """
        group_version_local = (
            "core/v1" if group_version.lower() == "v1" else group_version.lower()
        )
        kind_local = kind.split(".")[0] if "." in kind else kind

        # Check if the group version exists in the resources.
        logger.debug(
            f"looking for Kind {kind_local}: {group_version_local} in local api resources list..."
        )
        resource_kind: ResourceKind | None = None
        for group in K8sResourceDiscovery.api_resources:
            for version in group.versions:
                if version.group_version == group_version_local:
                    # Check if the kind exists in the resources of the version
                    resource_kind = self._find_resource_kind(
                        kind_local, version.resources
                    )
                    if resource_kind is not None:
                        break

        if resource_kind is None:
            raise ValueError(
                f"Invalid resource kind: {kind}. "
                f"Kind '{kind}' (Actual search: {kind_local}) not found in groupVersion '{group_version}'."
            )
        return resource_kind

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        after=after_log,
        reraise=True,
    )
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
        resource_kind = self._find_resource_kind(kind_local, resources)
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
            logger.warning(
                f"Error while getting resource statically "
                f"(group_version: {group_version}, kind: {kind}): {e}\n "
                f"Looking up dynamically..."
            )
            # If static lookup fails, try dynamic lookup.
            return self.get_resource_kind_dynamic(group_version, kind)
        except Exception as e:
            logger.error(
                f"Error while getting resource (group_version: {group_version}, kind: {kind}): {e}"
            )
            raise
