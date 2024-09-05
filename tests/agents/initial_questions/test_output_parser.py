from agents.initial_questions.output_parser import IOutputParser, QuestionOutputParser
import pytest

@pytest.mark.parametrize(
    "output,expected",
    [
        ("""Pod?
            Error?""",
         ["Pod?", "Error?"]),
        
        ("""1. Pod?
            2. Error?
            3. Namespace?
            4. Node?""",
         ["Pod?", "Error?", "Namespace?", "Node?"]),

        ("""
         
              1. Pod?
         

         """,
        ["Pod?"]),
    ]
)
def test_QuestionOutputParser(output: str, expected: list[str]):
    # Arrange:
    parser = QuestionOutputParser()

    # Act:
    result = parser.parse(output)

    # Assert:
    assert result == expected