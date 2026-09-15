from common.config import Config

from evaluation.validator.validator import (
    ChatOpenAIValidator,
    IValidator,
)


def create_validator(config: Config) -> IValidator:
    """Create the LLM-as-judge validator for the model selected by MODEL_NAME.

    The model must be listed under "models" in the config file; its entry provides
    the deployment id and temperature.
    """
    model_config = config.get_model_config(config.model_name)
    if "temperature" not in model_config:
        raise ValueError(
            f"Model '{config.model_name}' has no 'temperature' field -- "
            "it is not a chat model and cannot be used as an evaluation judge."
        )
    return ChatOpenAIValidator(
        model_config["name"],
        model_config["temperature"],
        model_config["deployment_id"],
    )
