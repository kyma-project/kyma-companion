from dotenv import load_dotenv
from llm_commons.langchain.proxy import ChatOpenAI, OpenAIEmbeddings
from llm_commons.proxy.base import set_proxy_version
import os
import json

load_dotenv()

## AI Core specific environment variables
AICORE_CONFIGURATION_ID_GPT35 = os.environ.get("AICORE_CONFIGURATION_ID_GPT35")
AICORE_DEPLOYMENT_ID_GPT35 = os.environ.get("AICORE_DEPLOYMENT_ID_GPT35")
AICORE_CONFIGURATION_ID_EMBEDDINGS_ADA = os.environ.get("AICORE_CONFIGURATION_ID_EMBEDDINGS_ADA")
AICORE_DEPLOYMENT_ID_EMBEDDINGS_ADA = os.environ.get("AICORE_DEPLOYMENT_ID_EMBEDDINGS_ADA")
AICORE_CONFIGURATION_ID_GPT4 = os.environ.get("AICORE_CONFIGURATION_ID_GPT4")
AICORE_DEPLOYMENT_ID_GPT4 = os.environ.get("AICORE_DEPLOYMENT_ID_GPT4")
AICORE_CONFIGURATION_ID_GPT4_32K = os.environ.get("AICORE_CONFIGURATION_ID_GPT4_32K")
AICORE_DEPLOYMENT_ID_GPT4_32K = os.environ.get("AICORE_DEPLOYMENT_ID_GPT4_32K")
AICORE_CONFIGURATION_ID_ADA = os.environ.get("AICORE_CONFIGURATION_ID_ADA")
AICORE_DEPLOYMENT_ID_ADA = os.environ.get("AICORE_DEPLOYMENT_ID_ADA")
AICORE_RESOURCE_GROUP = os.environ.get("AICORE_RESOURCE_GROUP")
AICORE_LLM_DEPLOYMENT_ID_GEMINI_PRO = os.environ.get("AICORE_DEPLOYMENT_ID_GEMINI_PRO")

# Parse SERVICE_URLS to get AI_API_URL
try:
    AICORE_LLM_API_BASE = json.loads(os.environ.get("AICORE_SERVICE_URLS"))["AI_API_URL"]
    os.environ["AICORE_LLM_API_BASE"] = AICORE_LLM_API_BASE
except:
    exit("AICORE_LLM_API_BASE is not set")

set_proxy_version('aicore')


class LLMModel:
    def __init__(self, deployment_id: str, model_name: str):
        self.deployment_id = deployment_id
        self.model_name = model_name


LLM_AZURE_GPT35 = "llm_azure_gpt35-turbo"
LLM_AZURE_EMBEDDINGS_ADA = "llm_azure_text-embedding-ada-002"
LLM_AZURE_GPT4 = "llm_azure_gpt4"
LLM_AZURE_GPT4_STREAMING = "llm_azure_gpt4_streaming"
LLM_AZURE_GPT4_32K_STREAMING = "llm_azure_gpt4-32k_streaming"
LLM_GEMINI_1_0_PRO = "gemini-1.0-pro"


def create_model(model_name, temperature=0):
    if model_name == LLM_AZURE_GPT35:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT35,
                          config_id=AICORE_CONFIGURATION_ID_GPT35,
                          temperature=temperature)
    elif model_name == LLM_AZURE_EMBEDDINGS_ADA:
        return OpenAIEmbeddings(deployment_id=AICORE_DEPLOYMENT_ID_EMBEDDINGS_ADA,
                                config_id=AICORE_CONFIGURATION_ID_EMBEDDINGS_ADA)
    elif model_name == LLM_AZURE_GPT4:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT4,
                          config_id=AICORE_CONFIGURATION_ID_GPT4,
                          verbose=False,
                          temperature=temperature)
    elif model_name == LLM_AZURE_GPT4_STREAMING:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT4,
                          config_id=AICORE_CONFIGURATION_ID_GPT4,
                          verbose=False,
                          streaming=True,
                          temperature=temperature)
    elif model_name == LLM_AZURE_GPT4_32K_STREAMING:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT4_32K,
                          config_id=AICORE_CONFIGURATION_ID_GPT4_32K,
                          verbose=False,
                          streaming=True,
                          temperature=temperature)
    return None
