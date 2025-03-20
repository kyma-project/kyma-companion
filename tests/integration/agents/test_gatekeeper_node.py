import pytest
from deepeval import assert_test
from deepeval.metrics import ConversationalGEval
from deepeval.test_case import ConversationalTestCase, LLMTestCase, LLMTestCaseParams
from langchain_core.messages import HumanMessage, SystemMessage

from integration.conftest import create_mock_state


# Correctness metric for not general queries that needs planning
@pytest.fixture
def gatekeeper_correctness_metric(evaluator_model):
    return ConversationalGEval(
        name="Correctness",
        evaluation_steps=[
            "Determine whether the actual output is similar to expected output.",
            "Irrespective of the input",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.8,
        verbose_mode=True,
    )


@pytest.mark.parametrize(
    "messages, expected_answer, expected_query_forwarding",
    [
        (
            # tests that the gatekeeper node corretly reply to greeting
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="Hi"),
            ],
            "Hello, how can I help you?",
            False,
        ),
        (
            # tests that the gatekeeper node corretly forward the query
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is problem with my deployment?"),
            ],
            "",
            True,
        ),
        (
            # tests that the gatekeeper node corretly forward the query
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is problem with my deployment?"),
            ],
            "",
            True,
        ),
        (
            # tests that the gatekeeper node corretly forward the query
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="how to deploy a kyma function?"),
            ],
            "",
            True,
        ),
        (
            # tests that the gatekeeper node corretly forward the query
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="what is the status of my api"),
            ],
            "",
            True,
        ),
        (
            # tests that the gatekeeper node corretly forward the query
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="what is the status of my pod"),
            ],
            "",
            True,
        ),
        (
            # tests that the gatekeeper node corretly decline a general non-technical query
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is the capital of Germany?"),
            ],
            "This question appears to be outside my domain of expertise. If you have any technical or Kyma related questions, I'd be happy to help.",
            False,
        ),
        (
            # tests that the gatekeeper node correctly answers a general programming related query
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content='Write "Hello, World!" code in Python'),
            ],
            'print("Hello, World!")',
            False,
        ),
        (
            # tests that the gatekeeper node correctly answers a general programming related query
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(
                    content='Write "Hello, World!" code in Python and what is the status of my deployment?'
                ),
            ],
            "",
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_invoke_gatekeeper_node(
    messages,
    expected_answer,
    expected_query_forwarding,
    companion_graph,
    gatekeeper_correctness_metric,
):
    """
    Tests that the invoke_gatekeeper_node method of CompanionGraph answers general queries as expected.
    """
    # Given: a conversation state with messages
    state = create_mock_state(messages)

    # When: the gatekeeper node's invoke_gatekeeper_node method is invoked
    result = await companion_graph._invoke_gatekeeper_node(state, messages[-1].content)

    if expected_query_forwarding:
        assert (
            result.forward_query
        ), "Query should be forwarded"  # query should be forwarded

    else:
        assert (
            not result.forward_query
        ), "Query should not be forwarded"  # query should not be forwarded
        # Then: we evaluate the direct response using deepeval metrics
        test_case = ConversationalTestCase(
            turns=[
                LLMTestCase(
                    input=messages[-1].content,
                    actual_output=result.direct_response,
                    expected_output=expected_answer,
                )
            ]
        )
        assert_test(test_case, [gatekeeper_correctness_metric])
