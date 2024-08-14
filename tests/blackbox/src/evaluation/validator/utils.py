from common.config import Config

from evaluation.validator.enums import AIModel
from evaluation.validator.validator import (
    ChatOpenAIValidator,
    ValidatorInterface,
)


def create_validator(config: Config) -> ValidatorInterface:
    if config.model_name == AIModel.CHATGPT_4_O:
        return ChatOpenAIValidator(config)

    raise ValueError(f"Unsupported model name: {config.model_name}")
