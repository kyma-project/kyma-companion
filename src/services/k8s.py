import base64
import copy
import os
import tempfile
from http import HTTPStatus
from typing import Protocol, cast, runtime_checkable

import requests
from kubernetes import client, dynamic

from services.data_sanitizer import IDataSanitizer
from utils import logging

logger = logging.get_logger(__name__)


@runtime_checkable
class IK8sClient(Protocol):
    """Interface for the K8sClient class."""

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
        """List all nodes metrics."""
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


class K8sClient:
    """Client to interact with the Kubernetes API."""

    api_server: str
    user_token: str
    certificate_authority_data: str
    ca_temp_filename: str = ""
    dynamic_client: dynamic.DynamicClient
    data_sanitizer: IDataSanitizer | None

    def __init__(
        self,
        api_server: str,
        user_token: str,
        certificate_authority_data: str,
        data_sanitizer: IDataSanitizer | None = None,
    ):
        """Initialize the K8sClient object."""
        self.api_server = api_server
        self.user_token = user_token
        self.certificate_authority_data = certificate_authority_data

        # Write the certificate authority data to a temporary file.
        ca_file = tempfile.NamedTemporaryFile(delete=False)
        ca_file.write(self._get_decoded_ca_data())
        ca_file.close()
        self.ca_temp_filename = ca_file.name

        self.dynamic_client = self._create_dynamic_client()

        self.data_sanitizer = data_sanitizer

    def __del__(self):
        """Destructor to remove the temporary file containing certificate authority data."""
        if self.ca_temp_filename != "":
            try:
                os.remove(self.ca_temp_filename)
            except FileNotFoundError:
                return

    def model_dump(self) -> None:
        """Dump the model. It should not return any critical information because it is called by checkpointer
        to store the object in database."""
        return None

    def _get_decoded_ca_data(self) -> bytes:
        """Decode the certificate authority data."""
        return base64.b64decode(self.certificate_authority_data)

    def _create_dynamic_client(self) -> dynamic.DynamicClient:
        """Create a dynamic client for the K8s API."""
        # Create configuration object for client.
        conf = client.Configuration()
        conf.host = self.api_server
        conf.api_key["authorization"] = self.user_token
        conf.api_key_prefix["authorization"] = "Bearer"
        conf.verify_ssl = True
        conf.ssl_ca_cert = self.ca_temp_filename

        return dynamic.DynamicClient(client.api_client.ApiClient(configuration=conf))

    def _get_auth_headers(self) -> dict:
        """Get the authentication headers for the Kubernetes API request."""
        return {
            "Authorization": "Bearer " + self.user_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def execute_get_api_request(self, uri: str) -> dict | list[dict]:
        """Execute a GET request to the Kubernetes API."""
        response = requests.get(
            url=f"{self.api_server}/{uri.lstrip('/')}",
            headers=self._get_auth_headers(),
            verify=self.ca_temp_filename,
        )

        if response.status_code != HTTPStatus.OK:
            raise ValueError(
                f"Failed to execute GET request to the Kubernetes API. Error: {response.text}"
            )

        if self.data_sanitizer:
            return self.data_sanitizer.sanitize(response.json())
        return response.json()  # type: ignore

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
        return list[dict](result["items"])  # type: ignore

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
        uri = (
            f"api/v1/namespaces/{namespace}/pods/{name}/log"
            f"?container={container_name}"
            f"&tailLines={tail_limit}"
        )

        if is_terminated:
            uri += "&previous=true"

        response = requests.get(
            url=f"{self.api_server}/{uri.lstrip('/')}",
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
