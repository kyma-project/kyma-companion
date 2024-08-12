from evaluation.validator.enums import AIModel
from evaluation.validator.validator import (
    ChatOpenAIValidator,
    ValidatorInterface,
)
from common.config import Config


def create_validator(config: Config) -> ValidatorInterface:
    if config.model_name == AIModel.CHATGPT_4_O:
        return ChatOpenAIValidator(config)

    raise ValueError(f"Unsupported model name: {config.model_name}")
