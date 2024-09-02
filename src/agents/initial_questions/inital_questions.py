from typing import Protocol

from langchain_core.prompts import PromptTemplate

from agents.initial_questions.prompts import INITIAL_QUESTIONS_PROMPT
from utils.models import IModel


class IInitialQuestionsAgent(Protocol):
    """Interface for InitialQuestionsAgent."""

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        ...


class InitialQuestionsAgent:
    """Agent that generates initial questions."""

    model: IModel
    prompt_template: str = INITIAL_QUESTIONS_PROMPT

    def __init__(self, model: IModel) -> None:
        self.model = model

    def generate_questions(self, context: str) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        # Format prompt and send to llm.
        prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=["context"],
        )
        prompt = prompt.format(context=context)
        result = self.model.invoke(prompt)

        # Extract questions from result.
        lines: list[str] = []
        for line in result.content.__str__().split("\n"):
            if line.strip() == "":
                continue
            lines.append(line)

        return lines
