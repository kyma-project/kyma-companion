import typing
from typing import Protocol

import tiktoken
from langchain_core.prompts import PromptTemplate

from agents.common.data import Message
from agents.common.utils import get_relevant_context_from_k8s_cluster
from initial_questions.output_parser import QuestionOutputParser
from initial_questions.prompts import INITIAL_QUESTIONS_PROMPT
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


class IInitialQuestionsHandler(Protocol):
    """Protocol for InitialQuestionsHandler."""

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        ...

    def fetch_relevant_data_from_k8s_cluster(
        self, message: Message, k8s_client: IK8sClient
    ) -> str:
        """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""
        ...

    def apply_token_limit(self, text: str, token_limit: int) -> str:
        """Reduces the amount of tokens of a string by truncating exeeding tokens.
        Takes the template into account."""
        ...


class IEncoding(Protocol):
    """Encodes strings to tokens and decodes tokens to strings"""

    def encode(self, text: str) -> list[int]:
        """Encodes strings to tokens;"""
        ...

    def decode(self, tokens: list[int]) -> str:
        """Decodes tokens to strings."""
        ...


class InitialQuestionsHandler:
    """Handler that generates initial questions."""

    _chain: typing.Any
    _model: IModel
    _template: str
    _tokenizer: IEncoding

    def __init__(
        self,
        model: IModel,
        template: str | None = None,
        tokenizer: IEncoding | None = None,
    ) -> None:
        self._model = model
        self._template = template or INITIAL_QUESTIONS_PROMPT
        prompt = PromptTemplate(
            template=self._template,
            input_variables=["context"],
        )
        output_parser = QuestionOutputParser()
        self._chain = prompt | model.llm | output_parser
        self._tokenizer = tokenizer or tiktoken.encoding_for_model(self._model.name)

    def apply_token_limit(self, text: str, token_limit: int) -> str:
        """Reduces the amount of tokens of a string by truncating exeeding tokens.
        Takes the template into account."""

        tokens_template = self._tokenizer.encode(text=self._template)
        template_token_count = len(tokens_template)
        tokens_text = self._tokenizer.encode(text=text)
        text_token_count = len(tokens_text)

        if template_token_count > token_limit:
            raise ValueError("Token limit is smaller than template token count")
        token_limit -= template_token_count

        if text_token_count > token_limit:
            tokens_text = tokens_text[:token_limit]

        return self._tokenizer.decode(tokens=tokens_text)

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        # Format prompt and send to llm.
        return self._chain.invoke({"context": context})  # type: ignore

    def fetch_relevant_data_from_k8s_cluster(
        self, message: Message, k8s_client: IK8sClient
    ) -> str:
        """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""

        return get_relevant_context_from_k8s_cluster(
            message=message, k8s_client=k8s_client
        )
