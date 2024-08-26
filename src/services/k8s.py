from kubernetes import client, dynamic
from abc import ABC, abstractmethod

import os
import base64
import tempfile
import requests


class K8sClientInterface(ABC):
    @abstractmethod
    def execute_get_api_request(self, uri: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_resource(self, api_version: str, kind: str, namespace: str) -> list:
        raise NotImplementedError

    @abstractmethod
    def get_resource(self, api_version: str, kind: str, name: str, namespace: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_not_running_pods(self, namespace: str) -> list:
        raise NotImplementedError

    @abstractmethod
    def list_nodes_metrics(self) -> list:
        raise NotImplementedError

    @abstractmethod
    def list_k8s_events(self, namespace: str) -> list:
        raise NotImplementedError

    @abstractmethod
    def list_k8s_warning_events(self, namespace: str) -> list:
        raise NotImplementedError


class K8sClient(K8sClientInterface):
    api_server: str
    user_token: str
    certificate_authority_data: str
    ca_temp_filename: str
    dynamic_client: dynamic.DynamicClient = None

    def __init__(self, api_server: str, user_token: str, certificate_authority_data: str):
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
        if self.ca_temp_filename != "":
            # TODO: check which one is correct
            os.remove(self.ca_temp_filename)
            # os.unlink(self.ca_temp_filename)

    def _get_decoded_ca_data(self) -> str:
        return base64.b64decode(self.certificate_authority_data)

    def _create_dynamic_client(self) -> dynamic.DynamicClient:
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

    def execute_get_api_request(self, uri: str) -> dict:
        # define headers for the API request
        headers = {
            "Authorization": "Bearer " + self.user_token,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Make the API request
        response = requests.get(
            url=f"{self.api_server}/{uri.lstrip('/')}",
            headers=headers,
            verify=self.ca_temp_filename
        )

        return response.json()

    def list_resource(self, api_version: str, kind: str, namespace: str) -> list:
        result = self.dynamic_client.resources.get(api_version=api_version, kind=kind).get(namespace=namespace)
        return result.items

    def get_resource(self, api_version: str, kind: str, name: str, namespace: str) -> dict:
        return self.dynamic_client.resources.get(api_version=api_version, kind=kind).get(name=name, namespace=namespace)

    def list_not_running_pods(self, namespace: str) -> list:
        all_pods = self.list_resource("v1", "Pod", namespace)
        return [pod for pod in all_pods if pod.status.phase != "Running"]

    def list_nodes_metrics(self) -> list:
        result = self.execute_get_api_request("apis/metrics.k8s.io/v1beta1/nodes")
        return list(result["items"])

    def list_k8s_events(self, namespace: str) -> list:
        uri = "api/v1/events?limit=500"
        if namespace != "":
            uri = f"api/v1/namespaces/{namespace}/events?limit=500"
        result = self.execute_get_api_request(uri)
        return list(result["items"])

    def list_k8s_warning_events(self, namespace: str) -> list:
        return [event for event in self.list_k8s_events(namespace) if event["type"] == "Warning"]
