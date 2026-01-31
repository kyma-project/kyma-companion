import asyncio
import base64
import copy
import os
import re
import ssl
import tempfile
from enum import Enum
from http import HTTPStatus
from typing import Any, Protocol, cast, runtime_checkable
from urllib.parse import urlparse

import aiohttp
from kubernetes import client, dynamic
from pydantic import BaseModel

from services.data_sanitizer import IDataSanitizer
from utils import logging
from utils.exceptions import K8sClientError, parse_k8s_error_response
from utils.settings import (
    ALLOWED_K8S_DOMAINS,
    K8S_API_PAGINATION_LIMIT,
    K8S_API_PAGINATION_MAX_PAGE,
)

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
    allowed_domains: list[str] = ALLOWED_K8S_DOMAINS

    def validate_headers(self) -> None:
        """Validate the Kubernetes API authentication headers."""
        if self.x_cluster_url == "":
            raise ValueError("x-cluster-url header is required.")
        if not self.is_cluster_url_allowed():
            raise ValueError(f"Cluster URL {self.x_cluster_url} is not allowed.")
        if self.x_cluster_certificate_authority_data == "":
            raise ValueError("x-cluster-certificate-authority-data header is required.")
        if self.x_k8s_authorization is None and (
            self.x_client_certificate_data is None or self.x_client_key_data is None
        ):
            raise ValueError(
                "Either x-k8s-authorization header or "
                "x-client-certificate-data and x-client-key-data headers are required."
            )

    def is_cluster_url_allowed(self) -> bool:
        """Check if the cluster URL is allowed based on the allowed domains."""
        if len(self.allowed_domains) == 0:
            logger.warning("ALLOWED_K8S_DOMAINS is empty. Skipping cluster URL validation.")
            return True

        try:
            # parse the URL to get the domain
            parsed_url = urlparse(self.x_cluster_url)
            if not parsed_url or not parsed_url.hostname:
                raise ValueError("Failed to parse. Invalid cluster URL format.")

            domain = parsed_url.hostname.strip("/")
            # if hostname ends with any of the allowed domains, return True
            return any(
                domain.endswith(f".{allowed_domain}") or domain == allowed_domain
                for allowed_domain in self.allowed_domains
            )
        except Exception as e:
            raise ValueError(f"Failed to check if cluster_url: {self.x_cluster_url}  is allowed") from e

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

    async def execute_get_api_request(self, uri: str) -> dict | list[dict]:
        """Execute a GET request to the Kubernetes API."""
        ...

    def list_resources(self, api_version: str, kind: str, namespace: str) -> list:
        """List resources of a specific kind in a namespace."""
        ...

    async def get_resource(
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

    async def describe_resource(
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

    async def list_nodes_metrics(self) -> list[dict]:
        """List all node metrics."""
        ...

    def list_k8s_events(self, namespace: str) -> list[dict]:
        """List all Kubernetes events."""
        ...

    def list_k8s_warning_events(self, namespace: str) -> list[dict]:
        """List all Kubernetes warning events."""
        ...

    def list_k8s_events_for_resource(self, kind: str, name: str, namespace: str) -> list[dict]:
        """List all Kubernetes events for a specific resource."""
        ...

    async def fetch_pod_logs(
        self,
        name: str,
        namespace: str,
        container_name: str,
        is_terminated: bool,
        tail_limit: int,
    ) -> list[str]:
        """Fetch logs of Kubernetes Pod."""
        ...

    async def get_namespace(self, name: str) -> dict:
        """
        Fetch a specific Kubernetes namespace by name.

        Args:
            name: The name of the namespace.

        Returns:
            The namespace resource as a dictionary.

        Raises:
            ValueError: If the namespace is not found or the API call fails.
        """
        ...

    async def get_group_version(self, group_version: str) -> dict:
        """Get the group version of the Kubernetes API."""
        ...

    def get_data_sanitizer(self) -> IDataSanitizer | None:
        """Return the data sanitizer instance"""
        ...


def get_url_for_paged_request(base_url: str, continue_token: str) -> str:
    """Construct the URL for paginated requests."""
    separator = "&" if "?" in base_url else "?"
    query_params = f"{separator}limit={K8S_API_PAGINATION_LIMIT}" + (
        f"&continue={continue_token}" if continue_token else ""
    )
    return base_url + query_params


class K8sClient:
    """Client to interact with the Kubernetes API."""

    k8s_auth_headers: K8sAuthHeaders
    ca_temp_filename: str = ""
    client_cert_temp_filename: str = ""
    client_key_temp_filename: str = ""
    _dynamic_client: dynamic.DynamicClient | None
    data_sanitizer: IDataSanitizer | None
    api_client: Any

    @staticmethod
    def new(k8s_auth_headers: K8sAuthHeaders, data_sanitizer: IDataSanitizer | None = None) -> IK8sClient:
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
            ca_file.write(self.k8s_auth_headers.get_decoded_certificate_authority_data())
        self.ca_temp_filename = ca_file.name
        self.client_ssl_context = ssl.create_default_context(cafile=self.ca_temp_filename)

        if self.k8s_auth_headers.get_auth_type() == AuthType.CLIENT_CERTIFICATE:
            # Write the client certificate data to a temporary file.
            with tempfile.NamedTemporaryFile(delete=False) as client_cert_file:
                client_cert_file.write(self.k8s_auth_headers.get_decoded_client_certificate_data())
            self.client_cert_temp_filename = client_cert_file.name

            # Write the client key data to a temporary file.
            with tempfile.NamedTemporaryFile(delete=False) as client_key_file:
                client_key_file.write(self.k8s_auth_headers.get_decoded_client_key_data())
            self.client_key_temp_filename = client_key_file.name
            self.client_ssl_context.load_cert_chain(
                certfile=self.client_cert_temp_filename,
                keyfile=self.client_key_temp_filename,
            )

        # Delay dynamic_client creation until first use
        self._dynamic_client = None

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

    @property
    def dynamic_client(self) -> dynamic.DynamicClient:
        """Lazy initialization of dynamic client. Creates the client on first access."""
        if self._dynamic_client is None:
            self._dynamic_client = self._create_dynamic_client()
        return self._dynamic_client

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

        if self.k8s_auth_headers.get_auth_type() == AuthType.TOKEN and self.k8s_auth_headers.x_k8s_authorization:
            headers["Authorization"] = "Bearer " + self.k8s_auth_headers.x_k8s_authorization
        return headers

    async def _paginated_api_request(self, base_url: str) -> dict | list[dict]:
        """Pagination support for the api request."""
        async with aiohttp.ClientSession(headers=self._get_auth_headers()) as session:
            # Initialize variables for pagination
            page_count = 0
            all_items: list[dict] = []
            continue_token = ""

            # loop until all items are fetched or continue token is empty.
            while True:
                page_count += 1

                # Check if we've exceeded the maximum number of pages
                if page_count > K8S_API_PAGINATION_MAX_PAGE:
                    err_msg = (
                        "Kubernetes API rate limit exceeded. Please refine your query and "
                        "provide more specific resource details."
                    )
                    logger.debug(err_msg)
                    raise ValueError(err_msg)

                # fetch the next batch of items.
                next_url = get_url_for_paged_request(base_url, continue_token)
                async with session.get(url=next_url, ssl=self.client_ssl_context) as response:
                    # Check if the response status is not OK.
                    if response.status != HTTPStatus.OK:
                        error_text = await response.text()
                        error_message = parse_k8s_error_response(error_text)
                        raise K8sClientError(
                            message=f"Failed to execute GET request to the Kubernetes API. Error: {error_message}",
                            status_code=response.status,
                            uri=base_url,
                        )

                    result = await response.json()
                    if "items" not in result:
                        return all_items if len(all_items) else result

                    if len(result["items"]) > 0:
                        all_items.extend(result["items"])

                    # Check for continue token
                    continue_token = result.get("metadata", {}).get("continue", "")
                    if not continue_token:
                        return all_items if len(all_items) else result

    async def execute_get_api_request(self, uri: str) -> dict | list[dict]:
        """Execute a GET request to the Kubernetes API"""
        base_url = f"{self.get_api_server()}/{uri.lstrip('/')}"
        logger.debug(f"Executing GET request to {base_url}")
        result = await self._paginated_api_request(base_url)
        logger.debug(f"Completed Executing GET request to {base_url}")

        # Validate result type
        if not isinstance(result, (list, dict)):
            raise K8sClientError(
                message=f"Invalid result type: {type(result)}",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                uri=uri,
            )

        if self.data_sanitizer:
            result = self.data_sanitizer.sanitize(result)
        return result

    def list_resources(self, api_version: str, kind: str, namespace: str) -> list[dict]:
        """List resources of a specific kind in a namespace.
        Provide empty string for namespace to list resources in all namespaces."""
        result = self.dynamic_client.resources.get(api_version=api_version, kind=kind).get(namespace=namespace)

        # convert objects to dictionaries.
        items = [item.to_dict() for item in result.items]
        if self.data_sanitizer:
            return self.data_sanitizer.sanitize(items)  # type: ignore
        return items

    async def get_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
        namespace: str,
    ) -> dict:
        """Get a specific resource by name in a namespace."""
        # Construct API path based on resource type
        # For core API (v1), use "api/v1"
        # For other APIs, use "apis/{api_version}"
        api_prefix = "api/v1" if api_version == "v1" else f"apis/{api_version}"

        # Get resource info to determine if it's namespaced
        resource_client = self.dynamic_client.resources.get(api_version=api_version, kind=kind)

        # Build URI
        if resource_client.namespaced:
            uri = f"{api_prefix}/namespaces/{namespace}/{resource_client.name}/{name}"
        else:
            uri = f"{api_prefix}/{resource_client.name}/{name}"

        result = await self.execute_get_api_request(uri)

        # execute_get_api_request already handles sanitization
        return cast(dict, result)

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

    async def describe_resource(
        self,
        api_version: str,
        kind: str,
        name: str,
        namespace: str,
    ) -> dict:
        """Describe a specific resource by name in a namespace. This includes the resource and its events."""
        resource = await self.get_resource(api_version, kind, name, namespace)

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
            if "status" not in pod or "phase" not in pod["status"] or pod["status"]["phase"] != "Running":
                items.append(pod)
        return items

    async def list_nodes_metrics(self) -> list[dict]:
        """List all K8s Nodes metrics."""
        result = await self.execute_get_api_request("apis/metrics.k8s.io/v1beta1/nodes")
        return list[dict](result)

    def list_k8s_events(self, namespace: str) -> list[dict]:
        """List all Kubernetes events. Provide empty string for namespace to list all events."""

        result = self.dynamic_client.resources.get(api_version="v1", kind="Event").get(namespace=namespace)

        # convert objects to dictionaries and return.
        events = [event.to_dict() for event in result.items]
        if self.data_sanitizer:
            return list[dict](self.data_sanitizer.sanitize(events))
        return events

    def list_k8s_warning_events(self, namespace: str) -> list[dict]:
        """List all Kubernetes warning events. Provide empty string for namespace to list all warning events."""
        return [event for event in self.list_k8s_events(namespace) if event["type"] == "Warning"]

    def list_k8s_events_for_resource(self, kind: str, name: str, namespace: str) -> list[dict]:
        """List all Kubernetes events for a specific resource. Provide empty string for namespace to list all events."""
        events = self.list_k8s_events(namespace)
        result = []
        for event in events:
            if event["involvedObject"]["kind"] == kind and event["involvedObject"]["name"] == name:
                result.append(event)

        return result

    async def fetch_pod_logs(
        self,
        name: str,
        namespace: str,
        container_name: str,
        is_terminated: bool,
        tail_limit: int,
    ) -> list[str]:
        """Fetch logs of Kubernetes Pod with automatic retry and fallback.

        Flow:
        1. Determine strategy: Should we fetch current or previous logs?
        2. Try fetching with automatic fallback to previous logs on certain errors
        """
        # Step 1: Determine which logs to fetch based on pod state
        fetch_previous = await self._should_fetch_previous_logs(
            name, namespace, container_name, is_terminated
        )

        # Step 2: Fetch logs with automatic fallback if needed
        return await self._fetch_with_fallback(
            name=name,
            namespace=namespace,
            container_name=container_name,
            fetch_previous=fetch_previous,
            allow_fallback=(not is_terminated),
            tail_limit=tail_limit,
        )

    async def _should_fetch_previous_logs(
        self, name: str, namespace: str, container_name: str, is_terminated: bool
    ) -> bool:
        """Determine if we should fetch previous terminated container logs.

        Returns True if:
        - User explicitly requested terminated logs (is_terminated=True)
        - Pre-check indicates container is in a state where previous logs should be fetched
        """
        if is_terminated:
            return True

        # Check pod state to determine if previous logs should be fetched
        pod_state_info = await self._check_pod_state(name, namespace, container_name)

        if pod_state_info.get("should_use_previous", False):
            logger.info(
                f"Pod {name} container {container_name} is in state "
                f"{pod_state_info.get('state', 'unknown')}. Will fetch previous logs."
            )
            return True

        return False

    async def _fetch_with_fallback(
        self,
        name: str,
        namespace: str,
        container_name: str,
        fetch_previous: bool,
        allow_fallback: bool,
        tail_limit: int,
    ) -> list[str]:
        """Fetch logs with automatic fallback to previous logs on certain errors.

        Flow:
        1. First attempt: Fetch logs as determined by strategy
        2. On error: If eligible, fallback to previous terminated container logs
        3. If fallback fails: Raise the original error
        """
        # First attempt: Fetch with the determined strategy
        try:
            return await self._fetch_pod_logs_internal(
                name, namespace, container_name, fetch_previous, tail_limit
            )
        except K8sClientError as e:
            # Second attempt: Fallback to previous logs if conditions are met
            if allow_fallback and not fetch_previous and self._should_fallback_to_previous(e):
                logger.info(
                    f"First attempt failed for pod {name} container {container_name}. "
                    f"Attempting fallback to previous logs."
                )
                try:
                    return await self._fetch_pod_logs_internal(
                        name, namespace, container_name, is_terminated=True, tail_limit=tail_limit
                    )
                except K8sClientError:
                    # Fallback failed, will raise original error below
                    logger.warning(
                        f"Fallback to previous logs also failed for pod {name} container {container_name}"
                    )

            # Either no fallback attempted or fallback failed - raise original error
            raise

    async def _check_pod_state(self, name: str, namespace: str, container_name: str) -> dict[str, Any]:
        """Check pod state to determine the best strategy for fetching logs.

        Returns a dict with:
        - state: Current container state (running, waiting, terminated, unknown)
        - should_use_previous: Whether to fetch previous container logs
        - reason: Human-readable reason for the state
        """
        try:
            pod = await self.get_resource("v1", "Pod", name, namespace)
            container_statuses = pod.get("status", {}).get("containerStatuses", [])

            for container_status in container_statuses:
                if container_status.get("name") == container_name:
                    state_info = container_status.get("state", {})

                    # Check terminated state
                    if "terminated" in state_info:
                        terminated = state_info["terminated"]
                        reason = terminated.get("reason", "Terminated")
                        return {
                            "state": "terminated",
                            "should_use_previous": False,  # Already terminated, fetch current terminated logs
                            "reason": reason,
                        }

                    # Check waiting state
                    if "waiting" in state_info:
                        waiting = state_info["waiting"]
                        reason = waiting.get("reason", "Waiting")

                        # For CrashLoopBackOff, fetch previous logs
                        if reason in ("CrashLoopBackOff", "ImagePullBackOff"):
                            return {
                                "state": "waiting",
                                "should_use_previous": True,
                                "reason": reason,
                            }

                        return {
                            "state": "waiting",
                            "should_use_previous": False,
                            "reason": reason,
                        }

                    # Check running state
                    if "running" in state_info:
                        # Check if there was a previous restart
                        restart_count = container_status.get("restartCount", 0)
                        if restart_count > 0:
                            return {
                                "state": "running",
                                "should_use_previous": False,  # Running now, but previous logs available
                                "reason": f"Running (restarted {restart_count} times)",
                            }

                        return {
                            "state": "running",
                            "should_use_previous": False,
                            "reason": "Running",
                        }

            # Container not found in status
            return {
                "state": "unknown",
                "should_use_previous": False,
                "reason": "Container status not found",
            }

        except (K8sClientError, KeyError, TypeError, AttributeError) as e:
            # If we can't check the pod state, log and continue with normal flow
            logger.warning(f"Failed to check pod state for {name}/{container_name}: {e}")
            return {
                "state": "unknown",
                "should_use_previous": False,
                "reason": str(e),
            }

    def _should_fallback_to_previous(self, error: K8sClientError) -> bool:
        """Determine if we should fallback to previous container logs based on the error.

        Only falls back for specific errors that indicate the current container is unavailable
        but previous logs might exist (e.g., container crashed, restarted, or not yet started).
        """
        error_message = error.message.lower()

        # Specific K8s API error patterns that indicate previous logs might be available
        # Note: Patterns are checked against the full error message:
        # "Failed to fetch logs for pod {name} in namespace {namespace}
        #  with container {container_name}. Error: {error_message}"
        # The patterns match against the {error_message} portion from the Kubernetes API
        fallback_patterns = [
            r"container.*is waiting to start",  # Container not started yet
            r"container.*not found in pod",  # Container doesn't exist in pod spec (check container name)
            r"container.*in crashloopbackoff",  # Container is crash looping
            r"previous terminated container",  # Explicitly about terminated container
            r"container has not been created",  # Container creation pending
            r"container.*is in waiting state",  # Container waiting
            r"back-off.*container",  # CrashLoopBackOff variations
        ]

        # Check for specific patterns
        for pattern in fallback_patterns:
            if re.search(pattern, error_message):
                return True

        # Also check for 400 Bad Request status code with specific container-related errors
        # (but not other 4xx errors like 401 Unauthorized, 403 Forbidden, 404 Pod Not Found)
        if error.status_code == HTTPStatus.BAD_REQUEST:
            # Only fallback on 400 if the error is specifically about the container state
            container_state_indicators = [
                "terminated",
                "crashloopbackoff",
                "waiting",
            ]
            # Container must be present AND at least one state indicator to avoid false positives
            return "container" in error_message and any(
                indicator in error_message for indicator in container_state_indicators
            )

        return False

    def _is_retryable_error(self, error: K8sClientError) -> bool:
        """Determine if an error is retryable (transient failures)."""
        # Retry on 5xx server errors, 429 rate limiting, and 503 service unavailable
        return error.status_code in (
            HTTPStatus.TOO_MANY_REQUESTS,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        )

    async def _fetch_pod_logs_internal(
        self,
        name: str,
        namespace: str,
        container_name: str,
        is_terminated: bool,
        tail_limit: int,
    ) -> list[str]:
        """Internal method to fetch pod logs with specified parameters.

        Retries up to 3 times with exponential backoff (1s, 2s) on retryable errors
        (network timeouts, rate limiting, 5xx errors).
        """
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                return await self._fetch_pod_logs_no_retry(name, namespace, container_name, is_terminated, tail_limit)
            except K8sClientError as e:
                # Only retry K8sClientError if it's retryable (429, 5xx)
                if attempt >= max_attempts or not self._is_retryable_error(e):
                    raise

                # Calculate exponential backoff: 1s, 2s
                wait_time = 2 ** (attempt - 1)
                logger.warning(
                    f"Retrying fetch_pod_logs for pod {name} due to {type(e).__name__}: {e}. "
                    f"Attempt {attempt}/{max_attempts}. Waiting {wait_time}s..."
                )

                # Wait before retry
                await asyncio.sleep(wait_time)
            except (TimeoutError, aiohttp.ServerTimeoutError, aiohttp.ServerDisconnectedError) as e:
                # Only retry transient network errors
                if attempt >= max_attempts:
                    raise

                # Calculate exponential backoff: 1s, 2s
                wait_time = 2 ** (attempt - 1)
                logger.warning(
                    f"Retrying fetch_pod_logs for pod {name} due to {type(e).__name__}: {e}. "
                    f"Attempt {attempt}/{max_attempts}. Waiting {wait_time}s..."
                )

                # Wait before retry
                await asyncio.sleep(wait_time)

        # This line is logically unreachable (loop always returns or raises)
        # but mypy requires it to prove all code paths return
        raise AssertionError("Unreachable code")  # pragma: no cover

    async def _fetch_pod_logs_no_retry(
        self,
        name: str,
        namespace: str,
        container_name: str,
        is_terminated: bool,
        tail_limit: int,
    ) -> list[str]:
        """Fetch pod logs without retry logic (used internally by _fetch_pod_logs_internal)."""
        uri = f"api/v1/namespaces/{namespace}/pods/{name}/log?container={container_name}&tailLines={tail_limit}"
        # if the pod is terminated, then fetch the logs of last Pod.
        if is_terminated:
            uri += "&previous=true"

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.get_api_server()}/{uri.lstrip('/')}",
                headers=self._get_auth_headers(),
                ssl=self.client_ssl_context,
            ) as response,
        ):
            # Check if the response status is not OK.
            if response.status != HTTPStatus.OK:
                error_text = await response.text()
                error_message = parse_k8s_error_response(error_text)
                raise K8sClientError(
                    message=f"Failed to fetch logs for pod {name} in namespace {namespace} "
                    f"with container {container_name}. Error: {error_message}",
                    status_code=response.status,
                    uri=uri,
                )

            logs = []
            async for line_bytes in response.content:
                # Decode each line (assuming utf-8 encoding)
                line = line_bytes.decode("utf-8").strip()
                logs.append(line)

            if self.data_sanitizer:
                return self.data_sanitizer.sanitize(logs)  # type: ignore
            return logs

    async def get_namespace(self, name: str) -> dict:
        """
        Fetch a specific Kubernetes namespace by name.

        Args:
            name: The name of the namespace.

        Returns:
            The namespace resource as a dictionary.

        Raises:
            ValueError: If the namespace is not found or the API call fails.
        """
        uri = f"api/v1/namespaces/{name}"
        result = await self.execute_get_api_request(uri)
        if not isinstance(result, dict):
            raise ValueError(f"Failed to fetch namespace '{name}'.")
        return result

    async def get_group_version(self, group_version: str) -> dict:
        """Get the group version of the Kubernetes API."""
        parts_count = len(group_version.split(GROUP_VERSION_SEPARATOR))

        if group_version == "" or parts_count > GROUP_VERSION_PARTS_COUNT:
            raise ValueError(f"Invalid groupVersion: {group_version}. Expected format: v1 or <group>/<version>.")

        # for Core API group, the endpoint is "api/v1", for others "apis/<group>/<version>".
        uri = f"api/{group_version}"
        if parts_count == GROUP_VERSION_PARTS_COUNT:
            uri = f"apis/{group_version}"

        # fetch the result.
        result = await self.execute_get_api_request(uri)
        if not isinstance(result, dict):
            raise ValueError(
                f"Invalid response from Kubernetes API for group version {group_version}. "
                f"Expected a dictionary, but got {type(result)}."
            )
        return result

    def get_data_sanitizer(self) -> IDataSanitizer | None:
        """Get the data sanitizer."""
        return self.data_sanitizer
