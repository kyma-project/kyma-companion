import json

from pydantic import AliasChoices, BaseModel, Field

from utils import logging
from utils.settings import K8S_API_RESOURCES_JSON_FILE

logger = logging.get_logger(__name__)


class ResourceKind(BaseModel):
    """ResourceKind is a class that represents a kind of resource in Kubernetes."""

    name: str
    singular_name: str | None = Field(validation_alias=AliasChoices("singular_name", "singularName"), default=None)
    namespaced: bool  # defines if it is namespaced or cluster scoped resource
    kind: str
    verbs: list[str]
    categories: list[str] | None = None
    storage_version_hash: str | None = Field(
        validation_alias=AliasChoices("storage_version_hash", "storageVersionHash"),
        default=None,
    )


class Version(BaseModel):
    """Version is a class that represents a version of an API resource."""

    group_version: str = Field(validation_alias=AliasChoices("group_version", "groupVersion"))
    version: str
    resources: list[ResourceKind]


class PreferredVersion(BaseModel):
    """PreferredVersion is a class that represents the preferred version of an API resource."""

    group_version: str = Field(validation_alias=AliasChoices("group_version", "groupVersion"))
    version: str


class ApiResourceGroup(BaseModel):
    """ApiResourceGroup is a class that represents a group of API resources in Kubernetes."""

    api_version: str | None = Field(validation_alias=AliasChoices("api_version", "apiVersion"))
    kind: str | None
    name: str
    preferred_version: PreferredVersion = Field(validation_alias=AliasChoices("preferred_version", "preferredVersion"))
    server_address_by_client_cid_rs: str | list | None
    versions: list[Version]


class K8sResourceDiscovery:
    """
    K8sResourceDiscovery loads the static list of Kubernetes API resources.
    """

    # Class static variable to store API resources
    api_resources: list[ApiResourceGroup] = []

    @staticmethod
    def initialize() -> None:
        """Static method to initialize the K8sResourceDiscovery class."""
        # load the json file ./config/api_resources.json.
        if len(K8sResourceDiscovery.api_resources) == 0:
            logger.info(f"Loading API resources from file: {K8S_API_RESOURCES_JSON_FILE}")
            with open(K8S_API_RESOURCES_JSON_FILE) as f:
                items = json.load(f)
                K8sResourceDiscovery.api_resources = [ApiResourceGroup.model_validate(i) for i in items]
