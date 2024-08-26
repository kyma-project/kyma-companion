from kubernetes import client, config, dynamic
from kubernetes.dynamic import DynamicClient
from kubernetes.client import api_client

import base64

class K8s_Access: ### TODO: add Pydantic BaseModel
    K8S_API_SERVER: str # we can directly get this from the cluster
    K8S_USER_TOKEN: str
    CERTIFICATE_AUTHORITY_DATA: str
    _client: DynamicClient = None ### TODO: add getter and setter

    def __init__(self, K8S_API_SERVER: str, K8S_USER_TOKEN: str, CERTIFICATE_AUTHORITY_DATA: str):
        self.K8S_API_SERVER = K8S_API_SERVER
        self.K8S_USER_TOKEN = K8S_USER_TOKEN
        self.CERTIFICATE_AUTHORITY_DATA = CERTIFICATE_AUTHORITY_DATA
        self._client = self._getK8sDynamicClient()

    def _getCA(self) -> str:
        return base64.b64decode(self.CERTIFICATE_AUTHORITY_DATA)

    def _getK8sDynamicClient(self) -> DynamicClient:
        conf = client.Configuration()
        conf.api_key['authorization'] = self.K8S_USER_TOKEN
        conf.api_key_prefix['authorization'] = 'Bearer'
        conf.host = self.K8S_API_SERVER

        conf.verify_ssl = True
        conf.ssl_ca_cert = self._getCA().name

        return dynamic.DynamicClient(
            api_client.ApiClient(configuration=conf)
        )
    
    def _setClient(self) -> None:
        if self._client is None:
            self._client = "_getK8sDynamicClient"()
    
    def listResources(self,  api_version: str, kind: str, namespace: str) -> dict:
        return self._client.resources.get(api_version=api_version, kind=kind)

    def getResource(self, apiVersion: str, kind: str, name: str, namespace: str):
        return self._client.resources.get(api_version=apiVersion, kind=kind).get(name=name, namespace=namespace)
