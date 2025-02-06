from common.config import Config

from evaluation.validator.enums import AIModel
from evaluation.validator.validator import (
    ChatOpenAIValidator,
    IValidator,
)


def create_validator(config: Config) -> IValidator:
    if config.model_name == AIModel.CHATGPT_4_O_MINI:
        model_config = config.get_model_config(config.model_name)
        return ChatOpenAIValidator(
            model_config["name"],
            model_config["temperature"],
            model_config["deployment_id"],
        )

    raise ValueError(f"Unsupported model name: {config.model_name}")
