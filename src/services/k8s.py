import base64
import copy
import os
import tempfile
from typing import Protocol

import requests
from kubernetes import client, dynamic


class K8sClientInterface(Protocol):
    def execute_get_api_request(self, uri: str) -> dict:
        """Execute a GET request to the Kubernetes API."""
        ...

    def list_resources(self, api_version: str, kind: str, namespace: str) -> list:
        """List resources of a specific kind in a namespace."""
        ...

    def get_resource(self, api_version: str, kind: str, name: str, namespace: str) -> dict:
        """Get a specific resource by name in a namespace."""
        ... 

    def describe_resource(self, api_version: str, kind: str, name: str, namespace: str) -> list:
        """Describe a specific resource by name in a namespace. This includes the resource and its events."""
        ...

    def list_not_running_pods(self, namespace: str) -> list:
        """List all pods that are not in the Running phase"""
        ...

    def list_nodes_metrics(self) -> list:
        """List all nodes metrics."""
        ...

    def list_k8s_events(self, namespace: str) -> list:
        """List all Kubernetes events."""
        ...

    def list_k8s_warning_events(self, namespace: str) -> list:
        """List all Kubernetes warning events."""
        ...

    def list_k8s_events_for_resource(self, kind: str, name: str, namespace: str) -> list:
        """List all Kubernetes events for a specific resource."""
        ...

class K8sClient(K8sClientInterface):
    api_server: str
    user_token: str
    certificate_authority_data: str
    ca_temp_filename: str
    dynamic_client: dynamic.DynamicClient = None

    def __init__(self, api_server: str, user_token: str, certificate_authority_data: str):
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

    def __del__(self):
        """Destructor to remove the temporary file containing certificate authority data."""
        if self.ca_temp_filename != "":
            try:
                os.remove(self.ca_temp_filename)
            except FileNotFoundError:
                pass

    def _get_decoded_ca_data(self) -> str:
        """Decode the certificate authority data."""
        return base64.b64decode(self.certificate_authority_data)

    def _create_dynamic_client(self) -> dynamic.DynamicClient:
        """Create a dynamic client for the K8s API."""
        # Create configuration object for client.
        conf = client.Configuration()
        conf.host = self.api_server
        conf.api_key['authorization'] = self.user_token
        conf.api_key_prefix['authorization'] = 'Bearer'
        conf.verify_ssl = True
        conf.ssl_ca_cert = self.ca_temp_filename

        return dynamic.DynamicClient(
            client.api_client.ApiClient(configuration=conf)
        )

    def _get_auth_headers(self) -> dict:
        """Get the authentication headers for the Kubernetes API request."""
        return {
            "Authorization": "Bearer " + self.user_token,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def execute_get_api_request(self, uri: str) -> dict:
        """Execute a GET request to the Kubernetes API."""
        response = requests.get(
            url=f"{self.api_server}/{uri.lstrip('/')}",
            headers=self._get_auth_headers(),
            verify=self.ca_temp_filename
        )

        return response.json()

    def list_resources(self, api_version: str, kind: str, namespace: str) -> list:
        """List resources of a specific kind in a namespace.
        Provide empty string for namespace to list resources in all namespaces."""
        result = self.dynamic_client.resources.get(api_version=api_version, kind=kind).get(namespace=namespace)
        return result.items

    def get_resource(self, api_version: str, kind: str, name: str, namespace: str) -> dict:
        """Get a specific resource by name in a namespace."""
        return self.dynamic_client.resources.get(api_version=api_version, kind=kind).get(name=name, namespace=namespace)

    def describe_resource(self, api_version: str, kind: str, name:str, namespace: str) -> list:
        """Describe a specific resource by name in a namespace. This includes the resource and its events."""
        resource = self.get_resource(api_version, kind, name, namespace)

        # clone the object because we cannot modify the original object.
        result = copy.deepcopy(resource.to_dict())

        # get events for the resource.
        result["events"] = self.list_k8s_events_for_resource(kind, name, namespace)
        for event in result["events"]:
            del event["involvedObject"]
        return result

    def list_not_running_pods(self, namespace: str) -> list:
        """List all pods that are not in the Running phase.
        Provide empty string for namespace to list all pods."""
        all_pods = self.list_resources("v1", "Pod", namespace)
        return [pod for pod in all_pods if pod.status.phase != "Running"]

    def list_nodes_metrics(self) -> list:
        """List all nodes metrics."""
        result = self.execute_get_api_request("apis/metrics.k8s.io/v1beta1/nodes")
        return list(result["items"])

    def list_k8s_events(self, namespace: str) -> list:
        """List all Kubernetes events. Provide empty string for namespace to list all events."""
        uri = "api/v1/events?limit=500"
        if namespace != "":
            uri = f"api/v1/namespaces/{namespace}/events?limit=500"
        result = self.execute_get_api_request(uri)
        return list(result["items"])

    def list_k8s_warning_events(self, namespace: str) -> list:
        """List all Kubernetes warning events. Provide empty string for namespace to list all warning events."""
        return [event for event in self.list_k8s_events(namespace) if event["type"] == "Warning"]

    def list_k8s_events_for_resource(self, kind: str, name: str, namespace: str) -> list:
        """List all Kubernetes events for a specific resource. Provide empty string for namespace to list all events."""
        events = self.list_k8s_events(namespace)
        result = []
        for event in events:
            if event["involvedObject"]["kind"] == kind and event["involvedObject"]["name"] == name:
                result.append(event)

        return result
