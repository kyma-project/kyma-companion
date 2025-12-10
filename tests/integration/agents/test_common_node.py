import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from langchain_core.messages import HumanMessage, SystemMessage

from integration.conftest import create_mock_state
from integration.test_utils import BaseTestCase


class TestCase(BaseTestCase):
    def __init__(self, name: str, messages: list, expected_answer: str):
        super().__init__(name)
        self.messages = messages
        self.expected_answer = expected_answer


def create_test_cases():
    return [
        TestCase(
            "Should answer general non-technical query about geography",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is the capital of Germany?"),
            ],
            "Berlin",
        ),
        TestCase(
            "Should answer general programming query with code example",
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content='Write "Hello, World!" code in Python'),
            ],
            'Here is a simple "Hello, World!" program in Python: `print("Hello, World!")`',
        ),
    ]


@pytest.mark.parametrize("test_case", create_test_cases())
@pytest.mark.asyncio
async def test_invoke_common_node(
    test_case: TestCase, companion_graph, answer_relevancy_metric
):
    """
    Tests that the invoke_common_node method of CompanionGraph answers general queries as expected.
    """
    # Given: a conversation state with messages
    state = create_mock_state(test_case.messages)

    # When: the common node's invoke_common_node method is invoked
    result = await companion_graph._invoke_common_node(
        state, test_case.messages[-1].content
    )

    # Then: we evaluate the response using deepeval metrics
    llm_test_case = LLMTestCase(
        input=test_case.messages[-1].content,
        actual_output=result,
        expected_output=test_case.expected_answer,
    )
    assert_test(llm_test_case, [answer_relevancy_metric])
