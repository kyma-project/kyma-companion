import json

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from rag.query_generator import Queries, QueryGenerator
from utils.settings import MAIN_MODEL


@pytest.fixture(scope="session")
def correctness_metric(evaluator_model):
    return GEval(
        name="Correctness",
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        evaluation_steps=[
            "Check if the output contains multiple semantically similar queries",
            "Verify that each query is a valid question or search phrase",
            "Ensure queries capture different aspects of the original query",
        ],
        model=evaluator_model,
        threshold=0.7,
    )


@pytest.fixture(scope="session")
def query_generator(app_models):
    model = app_models[MAIN_MODEL]
    return QueryGenerator(model=model)


@pytest.mark.parametrize(
    "input_query,expected_queries",
    [
        pytest.param(
            "How to create a function in Kyma?",
            Queries(
                queries=[
                    "What are the steps to deploy a serverless function in Kyma?",
                    "How to create and configure a Kyma function?",
                    "Can you provide a guide on creating functions in a Kyma environment?",
                    "What are the different ways to define a function in Kyma?",
                ]
            ),
            id="Should generate variations for a technical query",
        ),
        pytest.param(
            "Why is my Kyma pod failing?",
            Queries(
                queries=[
                    "What are common reasons for pod failures?",
                    "How to diagnose pod issues?",
                    "What should I check when pods are not running?",
                    "Troubleshoot pod failures",
                ]
            ),
            id="Should handle troubleshooting queries",
        ),
        pytest.param(
            "How to secure applications in Kyma?",
            Queries(
                queries=[
                    "How to implement API security for Kyma applications?",
                    "What security features does Kyma offer for protecting APIs?",
                    "Best practices for securing applications in Kyma",
                    "Implementing security measures in Kyma applications",
                ]
            ),
            id="Should handle complex technical queries",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_queries(
    input_query, expected_queries, query_generator, correctness_metric
):
    """Test query generation with different types of queries."""
    # When: the query generator's generate_queries method is invoked
    response = await query_generator.agenerate_queries(input_query)

    # Then: the generated queries should match the expected format
    assert isinstance(response, Queries)
    assert len(response.queries) > 0

    response_json = json.dumps({"queries": response.queries}, indent=2)
    expected_json = json.dumps({"queries": expected_queries.queries}, indent=2)

    test_case = LLMTestCase(
        input=input_query,
        actual_output=response_json,
        expected_output=expected_json,
    )

    assert_test(test_case, [correctness_metric], run_async=False)
