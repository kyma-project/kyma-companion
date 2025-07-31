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
        # Regex pattern matches leading whitespace, digits, and a dot (e.g., "   1.", "\t2.", "3.")
        pattern = re.compile(r"^\s*\d+\.")
        questions = [
            # For each non-empty line:
            #   - Remove leading whitespace, numbers, and dot (e.g., "   1.")
            #   - Strip leading/trailing whitespace
            pattern.sub("", line).strip()
            for line in output.strip().split("\n")
            if line.strip()  # Skip empty lines
        ]
        return questions
