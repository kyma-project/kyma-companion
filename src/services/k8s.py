import base64
import copy
import os
import tempfile
from enum import Enum
from http import HTTPStatus
from typing import Any, Protocol, cast, runtime_checkable

import requests
from kubernetes import client, dynamic
from pydantic import BaseModel

from agents.common.constants import (
    K8S_API_PAGINATION_LIMIT,
    K8S_API_PAGINATION_MAX_PAGE,
)
from services.data_sanitizer import IDataSanitizer
from utils import logging

logger = logging.get_logger(__name__)


GROUP_VERSION_SEPARATOR = "/"
GROUP_VERSION_PARTS_COUNT = 2


class AuthType(str, Enum):
    """Status of the sub-task."""

    TOKEN = "token"
    CLIENT_CERTIFICATE = "client_certificate"
    UNKNOWN = "unknown"


class K8sAuthHeaders(BaseModel):
    """Model for Kubernetes API authentication headers."""

    x_cluster_url: str
    x_cluster_certificate_authority_data: str
    x_k8s_authorization: str | None = None
    x_client_certificate_data: str | None = None
    x_client_key_data: str | None = None

    def validate_headers(self) -> None:
        """Validate the Kubernetes API authentication headers."""
        if self.x_cluster_url == "":
            raise ValueError("x-cluster-url header is required.")
        if self.x_cluster_certificate_authority_data == "":
            raise ValueError("x-cluster-certificate-authority-data header is required.")
        if self.x_k8s_authorization is None and (
            self.x_client_certificate_data is None or self.x_client_key_data is None
        ):
            raise ValueError(
                "Either x-k8s-authorization header or "
                "x-client-certificate-data and x-client-key-data headers are required."
            )

    def get_auth_type(self) -> AuthType:
        """Get the authentication type."""
        if self.x_k8s_authorization:
            return AuthType.TOKEN
        if self.x_client_certificate_data and self.x_client_key_data:
            return AuthType.CLIENT_CERTIFICATE
        return AuthType.UNKNOWN

    def get_decoded_certificate_authority_data(self) -> bytes:
        """Decode the certificate authority data."""
        return base64.b64decode(self.x_cluster_certificate_authority_data)

    def get_decoded_client_certificate_data(self) -> bytes:
        """Decode the certificate authority data."""
        if self.x_client_certificate_data is None:
            raise ValueError("Client certificate data is not available.")
        return base64.b64decode(self.x_client_certificate_data)

    def get_decoded_client_key_data(self) -> bytes:
        """Decode the certificate authority data."""
        if self.x_client_key_data is None:
            raise ValueError("Client key data is not available.")
        return base64.b64decode(self.x_client_key_data)


@runtime_checkable
class IK8sClient(Protocol):
    """Interface for the K8sClient class."""

    def get_api_server(self) -> str:
        """Returns the URL of the Kubernetes cluster."""
        ...

    def model_dump(self) -> None:
        """Dump the model without any confidential data."""
        ...

    def execute_get_api_request(self, uri: str) -> dict | list[dict]:
        """Execute a GET request to the Kubernetes API."""
        ...

    def list_resources(self, api_version: str, kind: str, namespace: str) -> list:
        """List resources of a specific kind in a namespace."""
        ...

    def get_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
        namespace: str,
    ) -> dict:
        """Get a specific resource by name in a namespace."""
        ...

    def get_resource_version(self, kind: str) -> str:
        """Get the resource version for a given kind."""
        ...

    def describe_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
        namespace: str,
    ) -> dict:
        """Describe a specific resource by name in a namespace. This includes the resource and its events."""
        ...

    def list_not_running_pods(self, namespace: str) -> list[dict]:
        """List all pods that are not in the Running phase"""
        ...

    def list_nodes_metrics(self) -> list[dict]:
        """List all node metrics."""
        ...

    def list_k8s_events(self, namespace: str) -> list[dict]:
        """List all Kubernetes events."""
        ...

    def list_k8s_warning_events(self, namespace: str) -> list[dict]:
        """List all Kubernetes warning events."""
        ...

    def list_k8s_events_for_resource(
        self, kind: str, name: str, namespace: str
    ) -> list[dict]:
        """List all Kubernetes events for a specific resource."""
        ...

    def fetch_pod_logs(
        self,
        name: str,
        namespace: str,
        container_name: str,
        is_terminated: bool,
        tail_limit: int,
    ) -> list[str]:
        """Fetch logs of Kubernetes Pod."""
        ...

    def get_group_version(self, group_version: str) -> dict:
        """Get the group version of the Kubernetes API."""
        ...


class K8sClient:
    """Client to interact with the Kubernetes API."""

    k8s_auth_headers: K8sAuthHeaders
    ca_temp_filename: str = ""
    client_cert_temp_filename: str = ""
    client_key_temp_filename: str = ""
    dynamic_client: dynamic.DynamicClient
    data_sanitizer: IDataSanitizer | None
    api_client: Any

    @staticmethod
    def new(
        k8s_auth_headers: K8sAuthHeaders, data_sanitizer: IDataSanitizer | None = None
    ) -> IK8sClient:
        """Create a new instance of the K8sClient class."""
        return K8sClient(
            k8s_auth_headers=k8s_auth_headers,
            data_sanitizer=data_sanitizer,
        )

    def __init__(
        self,
        k8s_auth_headers: K8sAuthHeaders,
        data_sanitizer: IDataSanitizer | None = None,
    ):
        """Initialize the K8sClient object."""
        self.k8s_auth_headers = k8s_auth_headers

        with tempfile.NamedTemporaryFile(delete=False) as ca_file:
            ca_file.write(
                self.k8s_auth_headers.get_decoded_certificate_authority_data()
            )
        self.ca_temp_filename = ca_file.name

        if self.k8s_auth_headers.get_auth_type() == AuthType.CLIENT_CERTIFICATE:
            # Write the client certificate data to a temporary file.
            with tempfile.NamedTemporaryFile(delete=False) as client_cert_file:
                client_cert_file.write(
                    self.k8s_auth_headers.get_decoded_client_certificate_data()
                )
            self.client_cert_temp_filename = client_cert_file.name

            # Write the client key data to a temporary file.
            with tempfile.NamedTemporaryFile(delete=False) as client_key_file:
                client_key_file.write(
                    self.k8s_auth_headers.get_decoded_client_key_data()
                )
            self.client_key_temp_filename = client_key_file.name

        self.dynamic_client = self._create_dynamic_client()

        self.data_sanitizer = data_sanitizer

    def __del__(self):
        """Destructor to remove the temporary file containing certificates data."""
        if self.ca_temp_filename != "":
            try:
                os.remove(self.ca_temp_filename)
            except FileNotFoundError:
                return

        if self.client_cert_temp_filename != "":
            try:
                os.remove(self.client_cert_temp_filename)
            except FileNotFoundError:
                return

        if self.client_key_temp_filename != "":
            try:
                os.remove(self.client_key_temp_filename)
            except FileNotFoundError:
                return

    def get_api_server(self) -> str:
        """Returns the URL of the Kubernetes cluster."""
        return self.k8s_auth_headers.x_cluster_url

    def model_dump(self) -> None:
        """Dump the model. It should not return any critical information because it is called by checkpointer
        to store the object in database."""
        return None

    def _create_dynamic_client(self) -> dynamic.DynamicClient:
        """Create a dynamic client for the K8s API."""
        # Create configuration object for client.
        conf = client.Configuration()
        conf.host = self.get_api_server()
        conf.verify_ssl = True
        conf.ssl_ca_cert = self.ca_temp_filename

        if self.k8s_auth_headers.get_auth_type() == AuthType.CLIENT_CERTIFICATE:
            conf.cert_file = self.client_cert_temp_filename
            conf.key_file = self.client_key_temp_filename
        elif self.k8s_auth_headers.get_auth_type() == AuthType.TOKEN:
            conf.api_key_prefix["authorization"] = "Bearer"
            conf.api_key["authorization"] = self.k8s_auth_headers.x_k8s_authorization
        else:
            raise ValueError("Unknown authentication type.")

        self.api_client = client.api_client.ApiClient(configuration=conf)
        return dynamic.DynamicClient(self.api_client)

    def _get_auth_headers(self) -> dict:
        """Get the authentication headers for the Kubernetes API request."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if (
            self.k8s_auth_headers.get_auth_type() == AuthType.TOKEN
            and self.k8s_auth_headers.x_k8s_authorization
        ):
            headers["Authorization"] = (
                "Bearer " + self.k8s_auth_headers.x_k8s_authorization
            )
        return headers

    def _paginated_api_request(
        self, base_url: str, cert: tuple | None = None
    ) -> dict | list[dict]:
        """Pagination support for the api request."""
        # Initialize variables for pagination
        page_count = 0
        all_items: list[dict] = []
        continue_token = ""
        # Handle pagination
        while True:
            page_count += 1

            # Check if we've exceeded the maximum number of pages
            if page_count > K8S_API_PAGINATION_MAX_PAGE:
                raise ValueError(
                    "Kubernetes API rate limit exceeded. Please refine your query and "
                    "provide more specific resource details."
                )

            # Add continue token to URL if it exists
            query_params = f"?limit={K8S_API_PAGINATION_LIMIT}" + (
                f"&continue={continue_token}" if continue_token else ""
            )
            current_url = base_url + query_params

            response = requests.get(
                url=current_url,
                headers=self._get_auth_headers(),
                verify=self.ca_temp_filename,
                cert=cert,
            )

            if response.status_code != HTTPStatus.OK:
                raise ValueError(
                    f"Failed to execute GET request to the Kubernetes API. Error: {response.text}"
                )

            result = response.json()

            # Extract items if this is a list response
            if "items" in result:
                all_items.extend(result["items"])

                # Check for continue token
                continue_token = result.get("metadata", {}).get("continue", "")

                if not continue_token:
                    if all_items:  # if some resource found
                        return all_items
                    else:  # if no resource found
                        return result  # type: ignore

            else:
                return result  # type: ignore

    def execute_get_api_request(self, uri: str) -> dict | list[dict]:
        """Execute a GET request to the Kubernetes API"""
        cert = None
        if self.k8s_auth_headers.get_auth_type() == AuthType.CLIENT_CERTIFICATE:
            cert = (self.client_cert_temp_filename, self.client_key_temp_filename)
        base_url = f"{self.get_api_server()}/{uri.lstrip('/')}"

        result = self._paginated_api_request(base_url, cert)

        if self.data_sanitizer:
            result = self.data_sanitizer.sanitize(result)
        return result

    def list_resources(self, api_version: str, kind: str, namespace: str) -> list[dict]:
        """List resources of a specific kind in a namespace.
        Provide empty string for namespace to list resources in all namespaces."""
        result = self.dynamic_client.resources.get(
            api_version=api_version, kind=kind
        ).get(namespace=namespace)

        # convert objects to dictionaries.
        items = [item.to_dict() for item in result.items]
        if self.data_sanitizer:
            return self.data_sanitizer.sanitize(items)  # type: ignore
        return items

    def get_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
        namespace: str,
    ) -> dict:
        """Get a specific resource by name in a namespace."""
        resource = (
            self.dynamic_client.resources.get(api_version=api_version, kind=kind)
            .get(name=name, namespace=namespace)
            .to_dict()
        )
        if self.data_sanitizer:
            return cast(dict, self.data_sanitizer.sanitize(resource))
        return resource  # type: ignore

    def get_resource_version(self, kind: str) -> str:
        """Get the resource version for a given kind.

        Args:
            kind: The Kyma/Kubernetes resource kind (e.g. 'Function', 'TracePipeline', 'Pod', 'Deployment', etc.)

        Returns:
            The resource version as a string

        Raises:
            ValueError: If the resource kind is not found
        """

        if not kind:
            raise ValueError("Resource kind is required.")

        try:
            # Query the API server for the resource kind
            api_resources = self.dynamic_client.resources.search(kind=kind)
            if not api_resources:
                raise ValueError(f"Resource kind '{kind}' not found")

            # Get the first match (most accurate)
            resource = api_resources[0]

            # Return the API version
            return str(resource.group_version)
        except Exception as e:
            logger.error(f"Failed to get resource version for kind '{kind}': {str(e)}")
            raise ValueError(f"Failed to get resource version for kind '{kind}'") from e

    def describe_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
        namespace: str,
    ) -> dict:
        """Describe a specific resource by name in a namespace. This includes the resource and its events."""
        resource = self.get_resource(api_version, kind, name, namespace)

        # clone the object because we cannot modify the original object.
        result = copy.deepcopy(resource)

        # get events for the resource.
        result["events"] = self.list_k8s_events_for_resource(kind, name, namespace)
        for event in result["events"]:
            del event["involvedObject"]

        if self.data_sanitizer:
            return self.data_sanitizer.sanitize(result)  # type: ignore
        return result

    def list_not_running_pods(self, namespace: str) -> list[dict]:
        """List all pods that are not in the Running phase.
        Provide empty string for namespace to list all pods."""
        all_pods = self.list_resources(
            api_version="v1",
            kind="Pod",
            namespace=namespace,
        )
        # filter pods by status and convert object to dictionary.
        items = []
        for pod in all_pods:
            if (
                "status" not in pod
                or "phase" not in pod["status"]
                or pod["status"]["phase"] != "Running"
            ):
                items.append(pod)
        return items

    def list_nodes_metrics(self) -> list[dict]:
        """List all nodes metrics."""
        result = self.execute_get_api_request("apis/metrics.k8s.io/v1beta1/nodes")
        return list[dict](result)

    def list_k8s_events(self, namespace: str) -> list[dict]:
        """List all Kubernetes events. Provide empty string for namespace to list all events."""

        result = self.dynamic_client.resources.get(api_version="v1", kind="Event").get(
            namespace=namespace
        )

        # convert objects to dictionaries and return.
        events = [event.to_dict() for event in result.items]
        if self.data_sanitizer:
            return list[dict](self.data_sanitizer.sanitize(events))
        return events

    def list_k8s_warning_events(self, namespace: str) -> list[dict]:
        """List all Kubernetes warning events. Provide empty string for namespace to list all warning events."""
        return [
            event
            for event in self.list_k8s_events(namespace)
            if event["type"] == "Warning"
        ]

    def list_k8s_events_for_resource(
        self, kind: str, name: str, namespace: str
    ) -> list[dict]:
        """List all Kubernetes events for a specific resource. Provide empty string for namespace to list all events."""
        events = self.list_k8s_events(namespace)
        result = []
        for event in events:
            if (
                event["involvedObject"]["kind"] == kind
                and event["involvedObject"]["name"] == name
            ):
                result.append(event)

        return result

    def fetch_pod_logs(
        self,
        name: str,
        namespace: str,
        container_name: str,
        is_terminated: bool,
        tail_limit: int,
    ) -> list[str]:
        """Fetch logs of Kubernetes Pod. Provide is_terminated as true if the pod is not running."""
        uri = f"api/v1/namespaces/{namespace}/pods/{name}/log?container={container_name}&tailLines={tail_limit}"

        if is_terminated:
            uri += "&previous=true"

        response = requests.get(
            url=f"{self.get_api_server()}/{uri.lstrip('/')}",
            headers=self._get_auth_headers(),
            verify=self.ca_temp_filename,
        )
        if response.status_code != HTTPStatus.OK:
            raise ValueError(
                f"Failed to fetch logs for pod {name} in namespace {namespace} "
                f"with container {container_name}. Error: {response.text}"
            )

        logs = []
        for line in response.iter_lines():
            logs.append(str(line))
        return logs

    def get_group_version(self, group_version: str) -> dict:
        """Get the group version of the Kubernetes API."""
        parts_count = len(group_version.split(GROUP_VERSION_SEPARATOR))

        if group_version == "" or parts_count > GROUP_VERSION_PARTS_COUNT:
            raise ValueError(
                f"Invalid groupVersion: {group_version}. Expected format: v1 or <group>/<version>."
            )

        # for Core API group, the endpoint is "api/v1", for others "apis/<group>/<version>".
        uri = f"api/{group_version}"
        if parts_count == GROUP_VERSION_PARTS_COUNT:
            uri = f"apis/{group_version}"

        # fetch the result.
        result = self.execute_get_api_request(uri)
        if not isinstance(result, dict):
            raise ValueError(
                f"Invalid response from Kubernetes API for group version {group_version}. "
                f"Expected a dictionary, but got {type(result)}."
            )
        return result
