from common.config import Config

from evaluation.validator.enums import AIModel
from evaluation.validator.validator import (
    ChatOpenAIValidator,
    IValidator,
)


def create_validator(config: Config) -> IValidator:
    if config.model_name == AIModel.CHATGPT_4_O_MINI:
        return ChatOpenAIValidator(config)

    raise ValueError(f"Unsupported model name: {config.model_name}")
