import typing
from typing import Protocol

import yaml
from langchain_core.prompts import PromptTemplate

from agents.common.data import Message
from initial_questions.output_parser import QuestionOutputParser
from initial_questions.prompts import INITIAL_QUESTIONS_PROMPT
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.models import IModel
from utils.utils import is_empty_str, is_non_empty_str

logger = get_logger(__name__)


class IInitialQuestionsHandler(Protocol):
    """Protocol for InitialQuestionsHandler."""

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        ...

    def fetch_relevant_data_from_k8s_cluster(
        self, message: Message, k8s_client: IK8sClient
    ) -> str:
        """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""
        ...


class InitialQuestionsHandler:
    """Handler that generates initial questions."""

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

        logger.info("Fetching relevant data from k8s cluster")

        # Query the Kubernetes API to get the context.
        context = ""

        # If the namespace is not provided, and the resource Kind is 'cluster'
        # get an overview of the cluster
        # by fetching all not running pods,
        # all K8s Nodes metrics,
        # and all K8s events with warning type.
        if (
            is_empty_str(message.namespace)
            and str(message.resource_kind).lower() == "cluster"
        ):
            logger.info(
                "Fetching all not running Pods, Node metrics, and K8s Events with warning type"
            )
            pods = yaml.dump_all(k8s_client.list_not_running_pods(namespace=""))
            metrics = yaml.dump_all(k8s_client.list_nodes_metrics())
            events = yaml.dump_all(k8s_client.list_k8s_warning_events(namespace=""))

            context = f"{pods}\n{metrics}\n{events}"

        # If the namespace is provided, and the resource Kind is 'namespace'
        # get an overview of the namespace
        # by fetching all K8s events with warning type.
        elif (
            is_non_empty_str(message.namespace)
            and str(message.resource_kind).lower() == "namespace"
        ):
            logger.info("Fetching all K8s Events with warning type")
            context = yaml.dump_all(
                k8s_client.list_k8s_warning_events(namespace=str(message.namespace))
            )

        # If the namespace is not provided, but the resource Kind is
        # describe that resource.
        # If the namespace is empty, query not-namespaced resources.
        # Finally, get all events related to given resource.
        elif is_non_empty_str(message.resource_kind) and is_non_empty_str(
            message.resource_api_version
        ):
            logger.info(
                f"Fetching all entities of Kind {message.resource_kind} with API version {message.resource_api_version}"
            )
            resources = yaml.dump(
                k8s_client.describe_resource(
                    api_version=str(message.resource_api_version),
                    kind=str(message.resource_kind),
                    name=str(message.resource_name),
                    namespace=message.namespace if message.namespace else "",
                )
            )
            events = yaml.dump_all(
                k8s_client.list_k8s_events_for_resource(
                    kind=str(message.resource_kind),
                    name=str(message.resource_name),
                    namespace=message.namespace if message.namespace else "",
                )
            )

            context = f"{resources}\n{events}"

        else:
            raise Exception("Invalid message provided.")

        return context
