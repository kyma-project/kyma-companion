from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool
import os

from rag import RAG
from helpers.models import AICORE_LLM_DEPLOYMENT_ID_GEMINI_PRO, LLM_GEMINI_1_0_PRO
from clients.gemini_client import GeminiClient

from agents.prompt_templates import KUBERNETES_KUBECTL_PROMPT_TEMPLATE
from helpers.k8s_resources import extract_kubernetes_resources
from helpers.logging import LogUtil

logger = LogUtil.get_logger(__name__)

gemini_client = GeminiClient(deployment_id=AICORE_LLM_DEPLOYMENT_ID_GEMINI_PRO, model_name=LLM_GEMINI_1_0_PRO)

WEAVIATE_URL = os.getenv("WEAVIATE_URL")


class KubernetesResourceExtractionInputAgent(BaseModel):
    question: str = Field(description="A user question to extract Kubernetes native resources from the cluster")


kyma_btp_rag = RAG("./data/kyma_btp_docs", os.getenv("WEAVIATE_URL"))
kyma_os_rag = RAG("./data/kyma_os_docs", os.getenv("WEAVIATE_URL"))

KUBERNETES_TOOL_NAME = "Kubernetes API call"


def create_retrieve_kubernetes_resources_function(namespace: str):
    def retrieve_kubernetes_resources(question: str) -> str:
        kubectl_generation_prompt = f"{KUBERNETES_KUBECTL_PROMPT_TEMPLATE.format(question=question, namespace=namespace)}"
        kubectl_commands = gemini_client.invoke(messages=[{"role": "user", "content": kubectl_generation_prompt}])
        print("\nkubectl_commands: \n", kubectl_commands)

        resources = ""
        for command in kubectl_commands.splitlines():
            if command.startswith("kubectl"):
                resource = extract_kubernetes_resources(command)
                resources += resource + "\n---\n"
            else:
                logger.error(f"Command {command} is not a valid kubectl command")
        return resources

    return retrieve_kubernetes_resources


def create_kubernetes_extraction_tool(namespace: str):
    return StructuredTool.from_function(
        func=create_retrieve_kubernetes_resources_function(namespace),
        name=KUBERNETES_TOOL_NAME,
        description="Used if the question is about Kubernetes or Kubernetes native resources to query kubernetes API to"
                    " retrieve the Kubernetes native resources",
        args_schema=KubernetesResourceExtractionInputAgent,
        return_direct=False,
        # coroutine= ... <- you can specify an async method if desired as well
    )


class KymaDocSearchInput(BaseModel):
    # TODO: improve the description
    query: str = Field(
        description="action input extracted from the user query to search for open-source Kyma documentation")


def retrieve_kyma_os_doc(query: str) -> str:
    doc = kyma_os_rag.retrieve(query, "")
    return doc


KYMA_OS_TOOL_NAME = "Open-Source Kyma Documentation Search"


def create_kyma_documentation_extraction_tool():
    return StructuredTool.from_function(
        func=retrieve_kyma_os_doc,
        name=KYMA_OS_TOOL_NAME,
        description="Used to search for open-source Kyma documentation if the query is related to open-source Kyma",
        args_schema=KymaDocSearchInput,
        return_direct=False,
    )


class KymaBTPDocSearchInput(BaseModel):
    # TODO: improve the description
    query: str = Field(
        description="action input extracted from the query to search for BTP Kyma documentation")


def retrieve_btp_kyma_doc(query: str) -> str:
    doc = kyma_btp_rag.retrieve(query, "")
    return doc


KYMA_BTP_TOOL_NAME = "BTP Kyma Documentation Search"


def create_btp_kyma_documentation_extraction_tool():
    return StructuredTool.from_function(
        func=retrieve_btp_kyma_doc,
        name=KYMA_BTP_TOOL_NAME,
        description="Used to search for BTP Kyma documentation if the query is related to Kyma on BTP (Business "
                    "Technology Platform).",
        args_schema=KymaBTPDocSearchInput,
        return_direct=False,
    )
