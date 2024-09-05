from typing import Any, Protocol

import yaml
from langchain_core.prompts import PromptTemplate

from agents.common.data import Message
from agents.initial_questions.output_parser import QuestionOutputParser
from agents.initial_questions.prompts import INITIAL_QUESTIONS_PROMPT
from services.k8s import IK8sClient
from utils.models import IModel


class IInitialQuestionsAgent(Protocol):
    """Interface for InitialQuestionsAgent."""

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        ...

    async def fetch_relevant_data_from_k8s_cluster(
        self, message: Message, k8s_client: IK8sClient
    ) -> str:
        """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""
        ...


class InitialQuestionsAgent:
    """Agent that generates initial questions."""

    chain: any

    def __init__(
        self,
        model: IModel,
    ) -> None:
        prompt_template: str = INITIAL_QUESTIONS_PROMPT
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context"],
        )
        output_parser = QuestionOutputParser()
        self.chain = prompt | model.llm | output_parser

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        # Format prompt and send to llm.
        return self.chain.invoke({"context": context})

    def fetch_relevant_data_from_k8s_cluster(
        self, message: Message, k8s_client: IK8sClient
    ) -> str:
        """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""

        # Query the Kubernetes API to get the context.
        yaml_context: list[Any] = []

        # If namespace is not provided, and the resource Kind is 'cluster'
        # get an overview of the cluster
        # by fetching all not running pods,
        # all K8s Nodes metrics,
        # and all K8s events with warning type.
        if message.namespace is None and message.resource_kind.lower() == "cluster":
            yaml_context.append(
                k8s_client.list_not_running_pods(namespace=message.namespace)
            )
            yaml_context.append(k8s_client.list_nodes_metrics())
            yaml_context.append(
                k8s_client.list_k8s_warning_events(namespace=message.namespace)
            )

        # If namespace is provided, and the resource Kind is 'namespace'
        # get an overview of the namespace
        # by fetching all K8s events with warning type.
        elif (
            message.namespace is not None
            and message.resource_kind.lower() == "namespace"
        ):
            yaml_context.append(
                k8s_client.list_k8s_warning_events(namespace=message.namespace)
            )

        # If namespace is not provided, but the resource Kind is
        # get a detailed view of the cluster for the specified Kind
        # by fetching all resources of the specified kind,
        elif message.namespace is None and message.resource_kind is not None:
            yaml_context.append(
                k8s_client.list_resources(
                    api_version=message.resource_api_version,
                    kind=message.resource_kind,
                    namespace=message.namespace,
                )
            )
            yaml_context.append(
                k8s_client.list_k8s_events_for_resource(
                    kind=message.resource_kind,
                    name=message.resource_name,
                    namespace=message.namespace,
                )
            )

        # If namespace is provided, and the resource Kind is not 'namespace'
        # get a detailed view of the namespace for the specified Kind
        # by fetching the specified resource,
        # and all K8s events for the specified resource.
        elif message.namespace is not None and message.resource_kind is not None:
            yaml_context.append(
                k8s_client.get_resource(
                    api_version=message.resource_api_version,
                    kind=message.resource_kind,
                    name=message.resource_name,
                    namespace=message.namespace,
                )
            )
            yaml_context.append(
                k8s_client.list_k8s_events_for_resource(
                    kind=message.resource_kind,
                    name=message.resource_name,
                    namespace=message.namespace,
                )
            )
        else:
            raise Exception("Invalid message provided.")

        text_context = yaml.dump(yaml_context)

        # return "\n---\n".join(context)
        return text_context
