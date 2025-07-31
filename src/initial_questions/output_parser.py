import re
from typing import Protocol

from langchain_core.output_parsers import BaseOutputParser

# Compiled regex pattern that matches:
# - Optional leading whitespace (spaces or tabs)
# - One or more digits
# - A literal dot (.)
# Example matches: "1.", "   2.", "\t3."
PATTERN_NUMBER_LINE = re.compile(r"^\s*\d+\.")


class IOutputParser(Protocol):
    """Interface for OutputParser."""

    def parse(self, output: str) -> list[str]:
        """Parse the output and return the questions."""
        ...


class QuestionOutputParser(BaseOutputParser):
    """OutputParser for InitialQuestionsAgent."""

    def parse(self, output: str) -> list[str]:
        """Parse the output and return the questions."""

        questions = [
            PATTERN_NUMBER_LINE.sub("", line).strip()
            for line in output.strip().split("\n")
            if line.strip()  # Skip empty lines
        ]
        return questions
