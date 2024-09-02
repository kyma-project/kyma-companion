from typing import Protocol

import yaml
from langchain_core.prompts import PromptTemplate

from agents.common.data import Message
from agents.initial_questions.prompts import INITIAL_QUESTIONS_PROMPT
from services.k8s import K8sClientInterface
from utils.models import IModel


class IInitialQuestionsAgent(Protocol):
    """Interface for InitialQuestionsAgent."""

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        ...

    async def fetch_relevant_data_from_k8s_cluster(
        self, message: Message, k8s_client: K8sClientInterface
    ) -> str:
        """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""
        ...


class InitialQuestionsAgent:
    """Agent that generates initial questions."""

    model: IModel
    prompt_template: str = INITIAL_QUESTIONS_PROMPT

    def __init__(self, model: IModel) -> None:
        self.model = model

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        # Format prompt and send to llm.
        prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=["context"],
        )
        prompt = prompt.format(context=context)
        result = self.model.invoke(prompt)

        # Extract questions from result.
        lines: list[str] = []
        for line in result.content.__str__().split("\n"):
            if line.strip() == "":
                continue
            lines.append(line)

        return lines

    async def fetch_relevant_data_from_k8s_cluster(
        self, message: Message, k8s_client: K8sClientInterface
    ) -> str:
        """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""

        # Query the Kubernetes API to get the context.
        context: list[str] = []
        if message.namespace == "" and message.resource_kind.lower() == "cluster":
            # case: cluster overview.
            # fetch all not running pods.
            context.append(
                yaml.dump(k8s_client.list_not_running_pods(namespace=message.namespace))
            )

            # fetch all K8s Nodes metrics.
            context.append(yaml.dump(k8s_client.list_nodes_metrics()))

            # fetch all K8s events with warning type.
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_warning_events(namespace=message.namespace)
                )
            )

        elif message.namespace != "" and message.resource_kind.lower() == "namespace":
            # case: namespace overview
            # fetch all K8s events with warning type.
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_warning_events(namespace=message.namespace)
                )
            )

        elif message.namespace == "" and message.resource_kind != "":
            # case: cluster-scoped detailed view.
            # fetch all resources of the specified kind.
            context.append(
                yaml.dump(
                    k8s_client.list_resources(
                        api_version=message.resource_api_version,
                        kind=message.resource_kind,
                        namespace=message.namespace,
                    )
                )
            )
            # fetch all K8s events for the specified resource.
            context.append(
                yaml.dump(
                    k8s_client.list_k8s_events_for_resource(
                        kind=message.resource_kind,
                        name=message.resource_name,
                        namespace=message.namespace,
                    )
                )
            )
        elif message.namespace != "" and message.resource_kind != "":
            # case: namespace-scoped detail view.
            # fetch the specified resource.
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
            # fetch all K8s events for the specified resource.
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
