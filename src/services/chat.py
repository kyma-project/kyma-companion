import os
from abc import ABC, abstractmethod
from typing import Protocol

import yaml
from pydantic import BaseModel

from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from agents.supervisor.agent import Message, SupervisorAgent
from services.k8s import K8sClientInterface
from utils.logging import get_logger
from utils.models import create_llm
from services.conversations import get_questions

logger = get_logger(__name__)

GPT4O_MODEL = "gpt-4o"

class ConversationContext(BaseModel):
    resource_type: str
    resource_name: str
    namespace: str = ""

class ChatInterface(Protocol):
    """Interface for Chat service."""
    async def conversations(self, ctx: ConversationContext, k8s_client: K8sClientInterface) -> dict:
        ...

    async def handle_request(self, message: Message):
        ...


class Chat:
    """Chat service."""

    supervisor_agent = None

    def __init__(self):
        llm = create_llm(GPT4O_MODEL)
        memory = RedisSaver(
            async_connection=initialize_async_pool(url=f"{os.getenv('REDIS_URL')}/0")
        )
        self.supervisor_agent = SupervisorAgent(llm, memory)

    async def conversations(self, ctx: ConversationContext, k8s_client: K8sClientInterface) -> dict:
        """Initialize the chat"""
        logger.info(f"Initializing chat with namespace '{ctx.namespace}', resource_type '{ctx.resource_type}' and resource name {ctx.resource_name}")

        if ctx.resource_type == "namespace":
            ctx.namespace = ctx.resource_name

        # create the `kubectl` command for the given resource
        # define conditions
        is_cluster_scoped_resource = ctx.namespace == "" and ctx.resource_type != ""
        is_namespace_scoped_resource = ctx.namespace != "" and ctx.resource_type != ""
        is_namespace_overview = ctx.namespace != "" and ctx.resource_type == "namespace"
        is_cluster_overview = ctx.namespace == "" and ctx.resource_type == "cluster"

        context = list[str]
        if is_cluster_overview:
            # cluster overview
            context.append(yaml.dump(
                k8s_client.list_not_running_pods(namespace=ctx.namespace)
                ))
            context.append(
                yaml.dump(
                    k8s_client.list_nodes_metrics()
                    ))
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_warning_events(namespace=ctx.namespace)
                    ))
        elif is_namespace_overview:
            # namespace overview
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_warning_events(namespace=ctx.namespace)
                    ))
        elif is_cluster_scoped_resource:
            # cluster-scoped detail view
            context.append(
                yaml.dump(
                    k8s_client.list_resources(api_version="v1", kind='Pod', namespace=ctx.namespace)
                    ))
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_events_for_resource(kind=ctx, name=ctx.resource_name, namespace=ctx.namespace)
                    ))
        elif is_namespace_scoped_resource:
            # namespace-scoped detail view
            context.append(
                yaml.dump(
                    k8s_client.get_resource(api_version="v1", kind='Pod', name=ctx.resource_name, namespace=ctx.namespace)
                    ))
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_events_for_resource(kind='Pod', name=ctx.resource_name, namespace=ctx.namespace)
                    ))

        context = "\n".join(context)
        question = get_questions(context)

        return {"message: ": question}

    async def handle_request(self, message: Message):  # noqa: ANN201
        """Handle a request"""
        logger.info("Processing request...")

        async for chunk in self.supervisor_agent.astream(message):
            yield f"{chunk}\n\n".encode()
