from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agents.reducer.prompts import MESSAGES_SUMMARIZATION_PROMPT
from utils.models.factory import IModel, IModelFactory, ModelFactory, ModelType
from utils.singleton_meta import SingletonMeta


class SummarizationModelFactory(metaclass=SingletonMeta):
    """A factory singleton class to create summarization models and chains."""

    _model_factory: IModelFactory
    _models: dict[str, IModel | Embeddings]
    _chains: dict[str, Any]

    def __init__(
        self,
        model_factory: IModelFactory | None = None,
    ) -> None:
        self._model_factory = model_factory or ModelFactory()
        self._models = {}
        self._chains = {}

    def get_model(self, model_type: ModelType) -> IModel | Embeddings:
        """Get the model for the given model type."""
        # check if the model is already initialized. If not, initialize it.
        if model_type not in self._models:
            # initialize the requested model and add it to the cache.
            model = self._model_factory.create_model(model_type)
            self._models[model_type] = model
        # return the model.
        return self._models[model_type]

    def get_chain(self, model_type: ModelType) -> Any:
        """Get the chain for the given model type."""
        # check if the chain is already initialized. If not, initialize it.
        if model_type not in self._chains:
            # create a chat prompt template for summarization.
            llm_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", MESSAGES_SUMMARIZATION_PROMPT),
                    MessagesPlaceholder(variable_name="messages"),
                ]
            )
            # get the summarization model.
            self._chains[model_type] = llm_prompt | self.get_model(model_type).llm
        # return the chain.
        return self._chains[model_type]
