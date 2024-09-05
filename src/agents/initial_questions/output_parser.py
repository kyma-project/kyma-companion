from typing import Protocol

from langchain_core.output_parsers import BaseOutputParser

class IOutputParser(Protocol):
    """Interface for OutputParser."""

    def parse(self, output: str) -> list[str]:
        """Parse the output and return the questions."""
        ...

class QuestionOutputParser(BaseOutputParser[list[str]]):
    """OutputParser for InitialQuestionsAgent."""

    def parse(self, output: str) -> list[str]:
        """Parse the output and return the questions."""
        return output.strip().split("\n")
