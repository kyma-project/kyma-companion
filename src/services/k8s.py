import asyncio
import base64
import copy
import os
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
from services.k8s_constants import (
    FALLBACK_ERROR_PATTERNS,
    ContainerStateReason,
    ContainerStateType,
    LogSource,
    PodPhase,
)
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
            if "status" not in pod or "phase" not in pod["status"] or pod["status"]["phase"] != PodPhase.RUNNING:
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
        tail_limit: int,
    ) -> list[str]:
        """Fetch logs of Kubernetes Pod - attempts both current and previous logs.

        Strategy:
        1. Try fetching both current AND previous logs in parallel
        2. If we got any logs, return them with status headers
        3. If we got no logs, return diagnostic context or "resource not found"

        Always returns list[str], never raises errors.
        """
        # Step 1: Try fetching both current and previous logs in parallel
        current_task = asyncio.create_task(self._try_fetch_logs(name, namespace, container_name, False, tail_limit))
        previous_task = asyncio.create_task(self._try_fetch_logs(name, namespace, container_name, True, tail_limit))

        current_logs, current_error = await current_task
        previous_logs, previous_error = await previous_task

        # Step 2: Format results and add diagnostics if current logs failed
        result_lines = []

        # Current logs section
        if current_logs is not None:
            result_lines.append(f"# {LogSource.CURRENT.capitalize()} logs: Successfully fetched")
            result_lines.append("")
            result_lines.extend(current_logs)
        else:
            # Current logs failed - show status and add diagnostics
            result_lines.append(f"# {LogSource.CURRENT.capitalize()} logs: Not available")
            result_lines.append("")

            # Add diagnostic context to explain why current logs failed
            diagnostic_context = await self._gather_pod_diagnostic_context(name, namespace, container_name)
            if (
                diagnostic_context
                and isinstance(diagnostic_context, str)
                and "Failed to gather some diagnostic information" not in diagnostic_context
            ):
                result_lines.append("# Diagnostic Information:")
                result_lines.append("")
                for line in diagnostic_context.split("\n"):
                    result_lines.append(line)
            else:
                # Resource doesn't exist
                result_lines.append("# Resource Not Found:")
                result_lines.append("")
                result_lines.append(f"Pod '{name}' not found in namespace '{namespace}'.")
                result_lines.append("")
                result_lines.append("Please check:")
                result_lines.append("- Pod name is correct")
                result_lines.append("- Namespace is correct")
                result_lines.append("- Pod exists in the cluster")

        # Add separator
        result_lines.append("")

        # Previous logs section
        if previous_logs is not None:
            result_lines.append(f"# {LogSource.PREVIOUS.capitalize()} logs: Successfully fetched")
            result_lines.append("")
            result_lines.extend(previous_logs)
        else:
            # Previous logs not available - this is often expected
            if isinstance(previous_error, K8sClientError):
                if previous_error.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND):
                    result_lines.append(
                        f"# {LogSource.PREVIOUS.capitalize()} logs: Not available (container has not been restarted)"
                    )
                else:
                    result_lines.append(f"# {LogSource.PREVIOUS.capitalize()} logs: Failed to fetch")
            else:
                result_lines.append(f"# {LogSource.PREVIOUS.capitalize()} logs: Failed to fetch")

        return result_lines

    async def _gather_pod_diagnostic_context(self, name: str, namespace: str, container_name: str) -> str:
        """Gather diagnostic context when pod logs are unavailable.

        Collects information to help troubleshoot why logs failed:
        - Pod events (most useful for understanding failures)
        - Container status (state, restart count)
        - Init container status (if applicable)
        """
        context_parts = []

        try:
            # 1. Pod Events - Most important diagnostic information
            event_info = self._format_pod_events(name, namespace)
            context_parts.append(event_info)

            # 2. Pod Description - Container and Init Container Status
            pod_description = self.describe_resource(api_version="v1", kind="Pod", name=name, namespace=namespace)
            if pod_description:
                # Container Status
                container_info = self._format_container_status(pod_description, container_name)
                if container_info:
                    context_parts.append(container_info)

                # Init Container Status
                init_container_info = self._format_init_container_status(pod_description)
                if init_container_info:
                    context_parts.append(init_container_info)

        except Exception as e:
            # Don't let diagnostic gathering fail the whole operation
            context_parts.append(f"\nNote: Failed to gather some diagnostic information: {e}")

        return "\n".join(context_parts) if context_parts else "No diagnostic information available."

    def _format_pod_events(self, name: str, namespace: str) -> str:
        """Format pod events for diagnostic output."""
        events = self.list_k8s_events_for_resource(kind="Pod", name=name, namespace=namespace)
        if not events:
            return "No recent pod events found."

        lines = ["Recent Pod Events:"]
        # Show last 5 events, most recent first
        for event in events[-5:][::-1]:
            reason = event.get("reason", "Unknown")
            message = event.get("message", "")
            count = event.get("count", 1)
            event_line = f"  [{reason}]"
            if count > 1:
                event_line += f" (x{count})"
            event_line += f" {message}"
            lines.append(event_line)

        return "\n".join(lines)

    def _format_container_status(self, pod_description: dict, container_name: str) -> str | None:
        """Format container status information for diagnostic output."""
        container_statuses = pod_description.get("status", {}).get("containerStatuses", [])
        container_status = next(
            (cs for cs in container_statuses if cs.get("name") == container_name),
            None,
        )

        if not container_status:
            return None

        lines = [f"\nContainer '{container_name}' Status:"]

        # State information
        state = container_status.get("state", {})
        if ContainerStateType.WAITING.value in state:
            waiting = state[ContainerStateType.WAITING.value]
            lines.append("  State: Waiting")
            lines.append(f"  Reason: {waiting.get('reason', 'Unknown')}")
            if waiting.get("message"):
                lines.append(f"  Message: {waiting.get('message')}")
        elif ContainerStateType.TERMINATED.value in state:
            terminated = state[ContainerStateType.TERMINATED.value]
            lines.append("  State: Terminated")
            lines.append(f"  Reason: {terminated.get('reason', 'Unknown')}")
            lines.append(f"  Exit Code: {terminated.get('exitCode', 'Unknown')}")
            if terminated.get("message"):
                lines.append(f"  Message: {terminated.get('message')}")
        elif ContainerStateType.RUNNING.value in state:
            lines.append("  State: Running")

        # Restart count
        restart_count = container_status.get("restartCount", 0)
        lines.append(f"  Restart Count: {restart_count}")

        # Last termination state if available
        last_state = container_status.get("lastState", {})
        if ContainerStateType.TERMINATED.value in last_state:
            terminated = last_state[ContainerStateType.TERMINATED.value]
            lines.append(f"  Last Termination Reason: {terminated.get('reason', 'Unknown')}")
            lines.append(f"  Last Exit Code: {terminated.get('exitCode', 'Unknown')}")

        return "\n".join(lines)

    def _format_init_container_status(self, pod_description: dict) -> str | None:
        """Format init container status information for diagnostic output."""
        init_container_statuses = pod_description.get("status", {}).get("initContainerStatuses", [])
        if not init_container_statuses:
            return None

        failed_init = [ics for ics in init_container_statuses if not ics.get("ready", False)]
        if not failed_init:
            return None

        lines = ["\nInit Containers (Failed):"]
        for ics in failed_init:
            init_name = ics.get("name", "unknown")
            state = ics.get("state", {})
            if ContainerStateType.WAITING.value in state:
                reason = state[ContainerStateType.WAITING.value].get("reason", "Unknown")
                lines.append(f"  - {init_name}: Waiting ({reason})")
            elif ContainerStateType.TERMINATED.value in state:
                reason = state[ContainerStateType.TERMINATED.value].get("reason", "Unknown")
                exit_code = state[ContainerStateType.TERMINATED.value].get("exitCode", "Unknown")
                lines.append(f"  - {init_name}: Terminated ({reason}, exit code: {exit_code})")

        return "\n".join(lines)

    def _extract_failure_reason(self, error: K8sClientError) -> str:
        """Extract a concise, user-friendly reason from the error message."""
        error_message = error.message.lower()

        # Common patterns and their user-friendly descriptions
        if "crashloopbackoff" in error_message or "crash loop back off" in error_message:
            return f"container is in {ContainerStateReason.CRASH_LOOP_BACK_OFF} state"
        if "container not found" in error_message:
            return "container not found"
        if "container is waiting to start" in error_message or "waiting to start" in error_message:
            return "container is waiting to start"
        if "container is terminated" in error_message or "container has been terminated" in error_message:
            return "container has terminated"
        if "pod has terminated" in error_message or "pod has been terminated" in error_message:
            return "pod has terminated"

        # Default: use a generic message
        return "container is not ready"

    def _should_fallback_to_previous(self, error: K8sClientError) -> bool:
        """Determine if we should fallback to previous container logs based on the error.

        Only fallback for container-specific state issues, not general API errors.
        """
        error_message = error.message.lower()
        return any(indicator in error_message for indicator in FALLBACK_ERROR_PATTERNS)

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

    async def _try_fetch_logs(
        self,
        name: str,
        namespace: str,
        container_name: str,
        is_terminated: bool,
        tail_limit: int,
    ) -> tuple[list[str] | None, Exception | None]:
        """Try to fetch pod logs with automatic retry on transient errors.

        Returns:
            On success: (logs, None)
            On failure: (None, exception)

        Retries up to 3 times with exponential backoff (1s, 2s, 4s) on retryable errors
        (network timeouts, rate limiting, 5xx errors).
        """
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                logs = await self._fetch_pod_logs_no_retry(name, namespace, container_name, is_terminated, tail_limit)
                return (logs, None)  # Success
            except (K8sClientError, aiohttp.ClientError, TimeoutError, OSError) as e:
                # Check if we should retry
                # Retry network/timeout errors, or K8sClientError if it's retryable
                should_retry = self._is_retryable_error(e) if isinstance(e, K8sClientError) else True

                # If this is the last attempt or error is not retryable, return the error
                if attempt >= max_attempts or not should_retry:
                    return (None, e)

                # Calculate exponential backoff: 1s, 2s, 4s
                wait_time = min(2 ** (attempt - 1), 8)
                logger.warning(
                    f"Retrying fetch_pod_logs for pod {name} due to {type(e).__name__}: {e}. "
                    f"Attempt {attempt}/{max_attempts}. Waiting {wait_time}s..."
                )

                # Wait before retry
                await asyncio.sleep(wait_time)

        # This line should never be reached, but satisfies type checker
        return (None, K8sClientError(message=f"Failed to fetch pod logs for {name} after {max_attempts} attempts"))

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
