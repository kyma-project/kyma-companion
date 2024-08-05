from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI, OpenAIEmbeddings
from gen_ai_hub.proxy.native.google.clients import GenerativeModel


LLM_AZURE_GPT35 = "llm_azure_gpt35-turbo"
LLM_AZURE_GPT35_16K = "llm_azure_gpt35-turbo-16k"
LLM_AZURE_EMBEDDINGS_ADA = "llm_azure_text-embedding-ada-002"
LLM_AZURE_GPT4 = "llm_azure_gpt4"
LLM_AZURE_GPT4_32K = "llm_azure_gpt4-32k"
LLM_AZURE_GPT4_STREAMING = "llm_azure_gpt4_streaming"
LLM_AZURE_GPT4_32K_STREAMING = "llm_azure_gpt4-32k_streaming"
LLM_GEMINI_1_0_PRO = "gemini-1.0-pro"

proxy_client = get_proxy_client('gen-ai-hub')


class LLMModel:
    def __init__(self, deployment_id: str, model_name: str):
        self.deployment_id = deployment_id
        self.model_name = model_name


def create_model(model_name, temperature=0):
    if model_name == LLM_AZURE_GPT35:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT35,
                          proxy_client=proxy_client,
                          temperature=temperature)
    elif model_name == LLM_AZURE_GPT35_16K:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT35_16K,
                          proxy_client=proxy_client,
                          temperature=temperature)
    elif model_name == LLM_AZURE_EMBEDDINGS_ADA:
        return OpenAIEmbeddings(deployment_id=AICORE_DEPLOYMENT_ID_EMBEDDINGS_ADA,
                                proxy_client=proxy_client)
    elif model_name == LLM_AZURE_GPT4:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT4,
                          proxy_client=proxy_client,
                          verbose=False,
                          temperature=temperature)
    elif model_name == LLM_AZURE_GPT4_32K:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT4_32K,
                          proxy_client=proxy_client,
                          verbose=False,
                          temperature=temperature)
    elif model_name == LLM_AZURE_GPT4_STREAMING:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT4,
                          proxy_client=proxy_client,
                          verbose=False,
                          streaming=True,
                          temperature=temperature)
    elif model_name == LLM_AZURE_GPT4_32K_STREAMING:
        return ChatOpenAI(deployment_id=AICORE_DEPLOYMENT_ID_GPT4_32K,
                          proxy_client=proxy_client,
                          verbose=False,
                          streaming=True,
                          temperature=temperature)
    elif model_name == LLM_GEMINI_1_0_PRO:
        return GenerativeModel(proxy_client=proxy_client, **dict({'model_name': 'gemini-1.0-pro'}))
    return None
