import typing
from typing import Any, Protocol

import yaml
from langchain_core.prompts import PromptTemplate

from agents.common.data import Message
from agents.initial_questions.output_parser import QuestionOutputParser
from agents.initial_questions.prompts import INITIAL_QUESTIONS_PROMPT
from services.k8s import IK8sClient
from utils.models import IModel
from utils.utils import is_empty_str, is_non_empty_str


class IInitialQuestionsAgent(Protocol):
    """Interface for InitialQuestionsAgent."""

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        ...

    def fetch_relevant_data_from_k8s_cluster(
        self, message: Message, k8s_client: IK8sClient
    ) -> str:
        """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""
        ...


class InitialQuestionsAgent:
    """Agent that generates initial questions."""

    chain: typing.Any

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
        return self.chain.invoke({"context": context})  # type: ignore

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
        if (
            is_empty_str(message.namespace)
            and message.resource_kind.lower() == "cluster"
        ):
            yaml_context.append(k8s_client.list_not_running_pods(namespace=""))
            yaml_context.append(k8s_client.list_nodes_metrics())
            yaml_context.append(k8s_client.list_k8s_warning_events(namespace=""))

        # If namespace is provided, and the resource Kind is 'namespace'
        # get an overview of the namespace
        # by fetching all K8s events with warning type.
        elif (
            is_non_empty_str(message.namespace)
            and message.resource_kind.lower() == "namespace"
        ):
            yaml_context.append(
                k8s_client.list_k8s_warning_events(namespace=str(message.namespace))
            )

        # If namespace is not provided, but the resource Kind is
        # get a detailed view of the cluster for the specified Kind
        # by fetching all resources of the specified kind,
        elif (
            is_empty_str(message.namespace)
            and is_non_empty_str(message.resource_kind)
            and is_non_empty_str(message.resource_api_version)
        ):
            yaml_context.append(
                k8s_client.list_resources(
                    api_version=str(message.resource_api_version),
                    kind=str(message.resource_kind),
                    namespace="",
                )
            )
            yaml_context.append(
                k8s_client.list_k8s_events_for_resource(
                    kind=str(message.resource_kind),
                    name=str(message.resource_name),
                    namespace="",
                )
            )

        # If namespace is provided, and the resource Kind is not 'namespace'
        # get a detailed view of the namespace for the specified Kind
        # by fetching the specified resource,
        # and all K8s events for the specified resource.
        elif (
            is_non_empty_str(message.namespace)
            and is_non_empty_str(message.resource_kind)
            and message.resource_kind.lower() != "namespace"
            and is_non_empty_str(message.resource_api_version)
        ) and is_non_empty_str(message.resource_name):
            yaml_context.append(
                k8s_client.get_resource(
                    api_version=str(message.resource_api_version),
                    kind=str(message.resource_kind),
                    name=str(message.resource_name),
                    namespace=str(message.namespace),
                )
            )
            yaml_context.append(
                k8s_client.list_k8s_events_for_resource(
                    kind=str(message.resource_kind),
                    name=str(message.resource_name),
                    namespace=str(message.namespace),
                )
            )
        else:
            raise Exception("Invalid message provided.")

        return yaml.dump(yaml_context)
