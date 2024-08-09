from os import getenv

from dotenv import load_dotenv
from gen_ai_hub.proxy import get_proxy_client
from gen_ai_hub.proxy.langchain import ChatOpenAI

proxy_client = get_proxy_client("gen-ai-hub")


def get_models() -> list[ChatOpenAI]:
    """Returns a list of ChatOpenAI objects with the GPT-3.5 and GPT-4 models."""
    return [
        get_gpt35_model(),
        get_gpt4o_model(),
    ]


def get_gpt35_model() -> ChatOpenAI:
    """Returns a ChatOpenAI object with the GPT-3.5 model."""
    return ChatOpenAI(
        deployment_id=getenv("AICORE_DEPLOYMENT_ID_GPT35"),
        temperature=0,
    )


def get_gpt4o_model() -> ChatOpenAI:
    """Returns a ChatOpenAI object with the GPT-4 model."""
    return ChatOpenAI(
        deployment_id=getenv("AICORE_DEPLOYMENT_ID_GPT4"),
        temperature=0,
    )
