import re
from typing import Protocol

from langchain_core.output_parsers import BaseOutputParser


class IOutputParser(Protocol):
    """Interface for OutputParser."""

    def parse(self, output: str) -> list[str]:
        """Parse the output and return the questions."""
        ...


class QuestionOutputParser(BaseOutputParser):
    """OutputParser for InitialQuestionsAgent."""

    def parse(self, output: str) -> list[str]:
        """Parse the output and return the questions."""
        # Split the output into lines.
        output = output.strip().split("\n")
        # Remove empty lines and leading and trailing whitespaces.
        output = [line.strip() for line in output if line.strip()]
        # Remove leading numbers.
        output = [re.sub(r"^\d+\.", "", line).strip() for line in output]

        return output
