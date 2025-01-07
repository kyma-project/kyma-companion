from typing import Any

from utils.singleton_meta import SingletonMeta
from utils.models.factory import IModel, IModelFactory, ModelFactory, ModelType
from utils.logging import get_logger
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from agents.reducer.prompts import MESSAGES_SUMMARIZATION_PROMPT

logger = get_logger(__name__)

class SummarizationModelFactory(metaclass=SingletonMeta):
    """A factory singleton class to create summarization models."""

    _model_factory: IModelFactory
    _models: dict[str, IModel]
    _chains: dict[str, Any]

    def __init__(
        self,
        model_factory: IModelFactory | None = None,
    ) -> None:
        try:
            self._model_factory = model_factory or ModelFactory()
            self._models = {}
            # models = self._model_factory.create_models()
        except Exception as e:
            logger.error(f"Failed to initialize ModelFactory: {e}")
            raise

    def get_model(self, model_type: ModelType) -> IModel:
        """Get the model for the given model type."""
        # check if the model is already initialized. If not, initialize it.
        if model_type.name not in self._models:
            # initialize the requested model and add it to the cache.
            model = self._model_factory.create_model(model_type.name)
            self._models[model_type.name] = model
        # return the model.
        return self._models[model_type.name]

    def get_chain(self, model_type: ModelType) -> IModel:
        # check if the chain is already initialized. If not, initialize it.
        if model_type.name not in self._chains:
            # create a chat prompt template for summarization.
            llm_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", MESSAGES_SUMMARIZATION_PROMPT),
                    MessagesPlaceholder(variable_name="messages"),
                ]
            )
            # get the summarization model.
            self._chains[model_type.name] = llm_prompt | self.get_model(model_type).llm.get_num_tokens_from_messages()
        # return the chain.
        return self._chains[model_type.name]
