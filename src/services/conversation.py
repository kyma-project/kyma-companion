import os
import time
from collections.abc import AsyncGenerator
from typing import Protocol

import yaml

from agents.common.data import Message
from agents.graph import IGraph, KymaGraph
from agents.initial_questions.inital_questions import (
    IInitialQuestionsAgent,
    InitialQuestionsAgent,
)
from agents.memory.conversation_history import ConversationMessage, QueryType
from agents.memory.redis_checkpointer import IMemory, RedisSaver, initialize_async_pool
from services.k8s import K8sClientInterface
from utils.logging import get_logger
from utils.models import LLM, IModel, ModelFactory
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)

REDIS_URL = f"{os.getenv('REDIS_URL')}/0"


class IService(Protocol):
    """Service interface"""

    async def new_conversation(
        self, conversation_id: str, message: Message, k8s_client: K8sClientInterface
    ) -> list[str]:
        """Initialize a new conversation. Returns a list of initial questions."""
        ...

    def handle_request(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request for a conversation"""
        ...


class ConversationService(metaclass=SingletonMeta):
    """
    Implementation of the conversation service.
    This class is a singleton and should be used to handle the conversation.
    """

    kyma_graph: IGraph
    model_factory: ModelFactory
    model: IModel
    memory: IMemory
    init_questions_agent: IInitialQuestionsAgent

    def __init__(self):
        self.model_factory = ModelFactory()
        self.model = self.model_factory.create_model(LLM.GPT4O_MODEL)
        self.memory = RedisSaver(async_connection=initialize_async_pool(url=REDIS_URL))
        self.kyma_graph = KymaGraph(self.model, self.memory)
        self.init_questions_agent = InitialQuestionsAgent(model=self.model)

    async def new_conversation(
        self, conversation_id: str, message: Message, k8s_client: K8sClientInterface
    ) -> list[str]:
        """Initialize a new conversation."""
        logger.info(f"Initializing new conversation id: {conversation_id}.")

        # Generate initial questions for the specified resource.
        questions = await self.generate_initial_questions(
            conversation_id, message, k8s_client
        )

        # initialize the redis memory for the conversation.
        await self.memory.add_conversation_message(
            conversation_id,
            ConversationMessage(
                type=QueryType.INITIAL_QUESTIONS,
                query="",
                response="\n".join(questions),
                timestamp=time.time(),
            ),
        )

        return questions

    async def generate_initial_questions(
        self, conversation_id: str, message: Message, k8s_client: K8sClientInterface
    ) -> list[str]:
        """Initialize the chat"""
        logger.info(
            f"Initializing conversation ({conversation_id}) with namespace '{message.namespace}', "
            f"resource_type '{message.resource_kind}' and resource name {message.resource_name}"
        )

        # Fetch the Kubernetes context for the initial questions.
        k8s_context = await self._fetch_k8s_context_for_initial_questions(
            message, k8s_client
        )

        # Generate questions from the context using an LLM.
        return self.init_questions_agent.generate_questions(context=k8s_context)

    async def _fetch_k8s_context_for_initial_questions(
        self, message: Message, k8s_client: K8sClientInterface
    ) -> str:
        """Fetch the Kubernetes context for the initial questions."""
        if message.resource_kind == "namespace":
            message.namespace = message.resource_name

        # Define the conditions to create the Kubernetes cluster context.
        is_cluster_scoped_resource = (
            message.namespace == "" and message.resource_kind != ""
        )
        is_namespace_scoped_resource = (
            message.namespace != "" and message.resource_kind != ""
        )
        is_namespace_overview = (
            message.namespace != "" and message.resource_kind == "namespace"
        )
        is_cluster_overview = (
            message.namespace == "" and message.resource_kind == "cluster"
        )

        # Query the Kubernetes API to get the context.
        context: list[str] = []
        if is_cluster_overview:
            # cluster overview
            context.append(
                yaml.dump(k8s_client.list_not_running_pods(namespace=message.namespace))
            )
            context.append(yaml.dump(k8s_client.list_nodes_metrics()))
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_warning_events(namespace=message.namespace)
                )
            )
        elif is_namespace_overview:
            # namespace overview
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_warning_events(namespace=message.namespace)
                )
            )
        elif is_cluster_scoped_resource:
            # cluster-scoped detail view
            context.append(
                yaml.dump(
                    k8s_client.list_resources(
                        api_version=message.resource_api_version,
                        kind=message.resource_kind,
                        namespace=message.namespace,
                    )
                )
            )
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_events_for_resource(
                        kind=message.resource_kind,
                        name=message.resource_name,
                        namespace=message.namespace,
                    )
                )
            )
        elif is_namespace_scoped_resource:
            # namespace-scoped detail view
            context.append(
                yaml.dump(
                    k8s_client.get_resource(
                        api_version=message.resource_api_version,
                        kind=message.resource_kind,
                        name=message.resource_name,
                        namespace=message.namespace,
                    )
                )
            )
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_events_for_resource(
                        kind=message.resource_kind,
                        name=message.resource_name,
                        namespace=message.namespace,
                    )
                )
            )

        return "\n---\n".join(context)

    async def handle_request(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request"""
        logger.info("Processing request...")
        async for chunk in self.kyma_graph.astream(conversation_id, message):
            logger.debug(f"Sending chunk: {chunk}")
            yield f"{chunk}".encode()
