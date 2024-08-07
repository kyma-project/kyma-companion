from os import getenv

from dotenv import load_dotenv
from gen_ai_hub.proxy import get_proxy_client
from gen_ai_hub.proxy.langchain import ChatOpenAI

proxy_client = get_proxy_client("gen-ai-hub")


def get_gpt35_model() -> ChatOpenAI:
    """Returns a ChatOpenAI object with the GPT-3.5 model."""
    load_dotenv()
    return ChatOpenAI(
        deployment_id=getenv("AICORE_DEPLOYMENT_ID_GPT35"),
        temperature=0,
    )


def get_gpt4o_model() -> ChatOpenAI:
    """Returns a ChatOpenAI object with the GPT-4 model."""
    load_dotenv()
    return ChatOpenAI(
        deployment_id=getenv("AICORE_DEPLOYMENT_ID_GPT4"),
        temperature=0,
    )
