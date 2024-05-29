import subprocess
import os

from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool
from clients.gemini_client import GeminiClient
from helpers.models import AICORE_LLM_DEPLOYMENT_ID_GEMINI_PRO, LLM_GEMINI_1_0_PRO
from agents.prompt_templates import KYMA_KUBECTL_PROMPT_TEMPLATE
from helpers.k8s_resources import extract_kubernetes_resources

from helpers.logging import LogUtil

logger = LogUtil.get_logger(__name__)

gemini_client = GeminiClient(deployment_id=AICORE_LLM_DEPLOYMENT_ID_GEMINI_PRO, model_name=LLM_GEMINI_1_0_PRO)


class KymaResourceExtractionInput(BaseModel):
    question: str = Field(description="A user question to extract Kyma resources from the Kubernetes cluster. ")


class KymaResourceExtractionError(BaseModel):
    error: str = Field(
        description="Error message if Kyma resource extraction fails")


KYMA_RESOURCES_TOOL_NAME = "Kyma Resource Extraction Tool"


def create_extract_kyma_resources_function(namespace: str):
    def extract_kyma_resources(question: str) -> str:
        kubectl_generation_prompt = f"{KYMA_KUBECTL_PROMPT_TEMPLATE.format(question=question, namespace=namespace)}"
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
    return extract_kyma_resources


def create_kyma_resources_extraction_tool(namespace: str):
    return StructuredTool.from_function(
        func=create_extract_kyma_resources_function(namespace),
        name=KYMA_RESOURCES_TOOL_NAME,
        description="Used to retrieve Kyma resource(s) for a Kyma related question.",
        args_schema=KymaResourceExtractionInput,
        return_direct=False,
        error_schema=KymaResourceExtractionError,
    )
