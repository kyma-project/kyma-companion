import os
from typing import Protocol

import yaml
from common.logger import get_logger
from gen_ai_hub.proxy import get_proxy_client
from gen_ai_hub.proxy.langchain import ChatOpenAI
from gen_ai_hub.proxy.native.google.clients import GenerativeModel
from pydantic import BaseModel

logger = get_logger(__name__)

proxy_client = get_proxy_client("gen-ai-hub")


class ModelConfig(BaseModel):
    name: str
    deployment_id: str


class Model(Protocol):
    def invoke(self, content: str) -> str: ...

    @property
    def name(self) -> str: ...


class OpenAIModel(Model):
    _name: str
    model: ChatOpenAI

    def __init__(self, config: ModelConfig):
        self._name = config.name
        self.model = ChatOpenAI(deployment_id=config.deployment_id, proxy_client=proxy_client, temperature=0)

    def invoke(self, content: str) -> str:
        response = self.model.invoke(content)
        return response.content

    @property
    def name(self) -> str:
        return self._name


class GeminiModel(Model):
    _name: str
    model: GenerativeModel

    def __init__(self, config: ModelConfig):
        self._name = config.name
        self.model = GenerativeModel(
            proxy_client=proxy_client,
            model_name=config.name,
            deployment_id=config.deployment_id,
        )

    def invoke(self, content: str) -> str:
        content = [{"role": "user", "parts": [{"text": content}]}]
        response = self.model.generate_content(content)
        return response.text

    @property
    def name(self) -> str:
        return self._name


def get_models() -> list:
    models_config_path = os.getenv("MODEL_CONFIG_PATH", "./config/validation/models.yml")
    logger.info(f"Loading models from the config file: {models_config_path}")
    try:
        with open(models_config_path) as file:
            yaml_data = yaml.safe_load(file)
            models_config = [ModelConfig(**model) for model in yaml_data]
            llms: list[Model] = []
            for config in models_config:
                logger.info(f"Initializing model: {config.name}")
                if config.name.startswith("gpt"):
                    llms.append(OpenAIModel(config))
                elif config.name.startswith("gemini"):
                    llms.append(GeminiModel(config))
                else:
                    raise ValueError(f"Model {config.name} not supported.")
            logger.info(f"Loaded {len(llms)} models")
            return llms

    except Exception:
        logger.exception(f"Failed to load/initialize models specified in the config file: {models_config}")
        raise
