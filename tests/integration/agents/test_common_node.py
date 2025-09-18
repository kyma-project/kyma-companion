import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from langchain_core.messages import HumanMessage, SystemMessage

from integration.conftest import create_mock_state


@pytest.mark.parametrize(
    "messages, expected_answer",
    [
        (
            # tests that the Common node corretly answers a general non-technical query
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is the capital of Germany?"),
            ],
            "Berlin",
        ),
        (
            # tests that the Common node correctly answers a general programming related query
            [
                SystemMessage(
                    content=""
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content='Write "Hello, World!" code in Python'),
            ],
            'Here is a simple "Hello, World!" program in Python: `print("Hello, World!")`',
        ),
    ],
)
@pytest.mark.asyncio
async def test_invoke_common_node(
    messages, expected_answer, companion_graph, answer_relevancy_metric
):
    """
    Tests that the invoke_common_node method of CompanionGraph answers general queries as expected.
    """
    # Given: a conversation state with messages
    state = create_mock_state(messages)

    # When: the common node's invoke_common_node method is invoked
    result = await companion_graph._invoke_common_node(state, messages[-1].content)

    # Then: we evaluate the response using deepeval metrics
    test_case = LLMTestCase(
        input=messages[-1].content,
        actual_output=result,
        expected_output=expected_answer,
    )
    assert_test(test_case, [answer_relevancy_metric])
