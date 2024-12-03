import pytest
from deepeval.metrics.g_eval import GEval

from rag.query_generator import QueryGenerator
from utils.models.factory import ModelType


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
            "Check if the output is in valid JSON format with a string array",
        ],
        model=evaluator_model,
        threshold=0.7,
    )


@pytest.fixture(scope="session")
def query_generator(app_models):
    model = app_models[ModelType.GPT4O]
    return QueryGenerator(model=model)


@pytest.mark.parametrize(
    "input_query,expected_queries",
    [
        pytest.param(
            "How to deploy a function in Kyma?",
            {
                "queries": [
                    "What are the steps to deploy a serverless function in Kyma?",
                    "How to create and configure a Kyma function?",
                    "What is the process of deploying serverless workloads in Kyma?",
                    "Explain function deployment options in Kyma",
                ]
            },
            id="Should generate variations for a technical query",
        ),
        pytest.param(
            "Why is my Kyma pod failing?",
            {
                "queries": [
                    "What are common reasons for Kyma pod failures?",
                    "How to diagnose pod issues in Kyma?",
                    "What should I check when Kyma pods are not running?",
                    "Troubleshoot pod failures in Kyma environment",
                ]
            },
            id="Should handle troubleshooting queries",
        ),
        pytest.param(
            "How to configure authentication and secure APIs in Kyma?",
            {
                "queries": [
                    "What are the authentication methods available in Kyma?",
                    "How to implement API security in Kyma applications?",
                    "Explain Kyma's API Gateway security features",
                    "What is the process of securing endpoints in Kyma?",
                ]
            },
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
    result = await query_generator.agenerate_queries(input_query)

    # Then: the generated queries should match the expected format
    assert isinstance(result, dict)
    assert "queries" in result
    assert isinstance(result["queries"], list)
    assert len(result["queries"]) > 0

    # And: the generated queries should be semantically similar to expected queries
    similarity_score = await correctness_metric.evaluate_async(
        prediction=result["queries"],
        target=expected_queries["queries"],
    )
    assert similarity_score >= 0.7  # Adjust threshold as needed
