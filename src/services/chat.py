import os
from typing import Protocol

import yaml
from pydantic import BaseModel

from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from agents.supervisor.agent import Message, SupervisorAgent
from services.inital_questions import CONVERSATION_TEMPLATE, InitialQuestions
from services.k8s import K8sClientInterface
from utils.logging import get_logger
from utils.models import create_llm

logger = get_logger(__name__)

GPT4O_MODEL = "gpt-4o"

class ConversationContext(BaseModel):
    resource_kind: str
    resource_name: str
    resource_api_version: str = "" 
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
        logger.info(f"Initializing chat with namespace '{ctx.namespace}', resource_type '{ctx.resource_kind}' and resource name {ctx.resource_name}")

        if ctx.resource_kind == "namespace":
            ctx.namespace = ctx.resource_name

        # Define the conditions to create the Kubernetes cluster context.
        is_cluster_scoped_resource = ctx.namespace == "" and ctx.resource_kind != ""
        is_namespace_scoped_resource = ctx.namespace != "" and ctx.resource_kind != ""
        is_namespace_overview = ctx.namespace != "" and ctx.resource_kind == "namespace"
        is_cluster_overview = ctx.namespace == "" and ctx.resource_kind == "cluster"

        # Query the Kubernetes API to get the context.
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
                    k8s_client.list_resources(api_version=ctx.resource_api_version, kind=ctx.resource_kind, namespace=ctx.namespace)
                    ))
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_events_for_resource(kind=ctx.resource_kind, name=ctx.resource_name, namespace=ctx.namespace)
                    ))
        elif is_namespace_scoped_resource:
            # namespace-scoped detail view
            context.append(
                yaml.dump(
                    k8s_client.get_resource(api_version=ctx.resource_api_version, kind=ctx.resource_kind, name=ctx.resource_name, namespace=ctx.namespace)
                    ))
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_events_for_resource(kind=ctx.resource_kind, name=ctx.resource_name, namespace=ctx.namespace)
                    ))
        context = "\n".join(context)
        
        # Generate questions from the context using an LLM.
        llm = InitialQuestions(llm=InitialQuestions.get_gpt4o_instance()) 
        questions = llm.generate_questions(template=CONVERSATION_TEMPLATE, context=context)

        return {"message: ": questions}

    async def handle_request(self, message: Message):  # noqa: ANN201
        """Handle a request"""
        logger.info("Processing request...")

        async for chunk in self.supervisor_agent.astream(message):
            yield f"{chunk}\n\n".encode()
