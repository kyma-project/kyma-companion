import json
import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import InternalError, Part, TaskState, TextPart
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError

from agents.common.constants import ERROR_RESPONSE, RESPONSE_THINKING, RESPONSE_UNABLE_TO_PROCESS
from agents.common.data import Message as CompanionMessage
from agents.graph import CompanionGraph
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from utils.response import extract_info_from_response_chunk

logger = logging.getLogger(__name__)

EMPTY_STR = ""


class CompanionA2AExecutor(AgentExecutor):
    """A2A Executor that wraps the Kyma Companion graph."""

    def __init__(self, graph: CompanionGraph):
        super().__init__()
        self.graph = graph

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Core logic triggered by an incoming A2A Task or Message."""

        # 1. Extract user input and the current task from the A2A context
        query = context.get_user_input()
        task = context.current_task

        if not task:
            if context.message is None:
                raise ServerError(error=InternalError(message="No message provided"))
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        # 2. Extract metadata for K8s credentials
        # A2A clients should pass K8s credentials via message metadata
        msg_metadata: dict = {}
        if context.message and hasattr(context.message, "metadata") and context.message.metadata:
            msg_metadata = context.message.metadata

        # 3. Create a TaskUpdater to stream state back to the client
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # 4. Get or create K8s client from metadata
        try:
            await updater.update_status(
                TaskState.working,
                new_agent_text_message("Validating your request...", task.context_id, task.id),
            )

            k8s_config = msg_metadata.get("x-target-k8s", None)
            if not k8s_config:
                raise ValueError("No Kubernetes credentials found in message metadata under 'x-target-k8s'")
            if isinstance(k8s_config, str):
                k8s_config = json.loads(k8s_config)

            k8s_client = self._get_k8s_client(k8s_config)
        except ValueError as e:
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(
                    "Failed to initialize Kubernetes client: "
                    + str(e)
                    + " Please check the provided credentials and try again.",
                    task.context_id,
                    task.id,
                ),
            )
            return
        except Exception as e:
            logger.exception(f"Unexpected error initializing Kubernetes client: {e}")
            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(
                    "Failed to initialize Kubernetes client. Please check the provided credentials and try again.",
                    task.context_id,
                    task.id,
                ),
            )
            return

        # 5. Create Companion message format
        # Extract resource info from metadata.resource
        resource = msg_metadata.get("resource", {})
        if isinstance(resource, str):
            resource = json.loads(resource)
        companion_message = CompanionMessage(
            query=query,
            resource_kind=resource.get("kind", EMPTY_STR),
            resource_api_version=resource.get("api_version", EMPTY_STR),
            resource_name=resource.get("name", EMPTY_STR),
            namespace=resource.get("namespace", EMPTY_STR),
        )

        # Use task context_id as conversation_id for thread continuity
        conversation_id = task.context_id or task.id

        try:
            # 6. Update status to working
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(RESPONSE_THINKING, task.context_id, task.id),
            )

            # 7. Stream from CompanionGraph to the A2A Event Queue
            final_response = ""
            async for chunk in self.graph.astream(
                conversation_id=conversation_id,
                message=companion_message,
                k8s_client=k8s_client,
            ):
                # Parse the chunk and extract response content
                chunk_info = extract_info_from_response_chunk(chunk)
                if chunk_info is None:
                    logger.warning(f"Received chunk with no actionable content: {chunk}")
                    continue
                if chunk_info.error:
                    logger.error(f"Error in chunk response: {chunk_info.error}")
                    await updater.update_status(
                        TaskState.failed,
                        new_agent_text_message(
                            ERROR_RESPONSE,
                            task.context_id,
                            task.id,
                        ),
                    )
                    return
                if chunk_info.status:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(chunk_info.status, task.context_id, task.id),
                    )
                if chunk_info.final_response:
                    final_response = chunk_info.final_response

            # 8. Mark the A2A task as complete
            if final_response:
                await updater.add_artifact(
                    [Part(root=TextPart(text=final_response))],
                    name="response",
                )
                await updater.complete()
            else:
                await updater.update_status(
                    TaskState.failed,
                    new_agent_text_message(RESPONSE_UNABLE_TO_PROCESS, task.context_id, task.id),
                )
        except Exception as e:
            logger.exception(f"Error during CompanionGraph execution: {e}")
            raise ServerError(error=InternalError()) from e

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Logic to gracefully halt execution if the A2A client aborts."""
        if context.current_task:
            logger.info(f"Task {context.current_task.id} cancelled by client.")
        # CompanionGraph doesn't support cancellation currently

    def _get_k8s_client(self, k8s_config: dict) -> IK8sClient:
        """Get K8s client from metadata or use the injected one."""
        if not k8s_config:
            raise ValueError("No Kubernetes credentials provided in message metadata under 'x-target-k8s'")

        headers = K8sAuthHeaders(
            x_cluster_url=k8s_config.get("url", EMPTY_STR),
            x_cluster_certificate_authority_data=k8s_config.get("certificate-authority-data", EMPTY_STR),
            x_k8s_authorization=k8s_config.get("authorization", EMPTY_STR),
            x_client_certificate_data=k8s_config.get("client-certificate-data", EMPTY_STR),
            x_client_key_data=k8s_config.get("client-key-data", EMPTY_STR),
        )
        # Validate headers before creating client
        headers.validate_headers()

        if not headers.is_cluster_url_allowed():
            raise ValueError(
                f"Kubernetes cluster URL ({headers.x_cluster_url}) is not in the allowed list. "
                f"The agents is configured to only allow access to specific cluster URLs for security reasons."
            )

        # TODO: add the data_sanitizer to prevent sensitive data from being logged or exposed in errors.
        return K8sClient.new(headers, data_sanitizer=None)
