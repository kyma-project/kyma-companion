import pytest
from deepeval.evaluate import evaluate
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

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
def test_generate_queries(
    input_query, expected_queries, query_generator, correctness_metric
):
    # When
    result = query_generator.generate_queries(input_query)

    # Then
    test_case = LLMTestCase(
        input=input_query,
        actual_output=str(result.queries),
        expected_output=str(expected_queries["queries"]),
    )

    # Assert using DeepEval
    eval_results = evaluate(
        test_cases=[test_case],
        metrics=[correctness_metric],
    )

    # Assert all metrics pass
    assert all(
        result.success for result in eval_results.test_results
    ), "Not all metrics passed"

    # Additional assertions
    default_num_queries = 4
    assert len(result.queries) == default_num_queries
    assert all(isinstance(q, str) for q in result.queries)
    assert all(len(q.strip()) > 0 for q in result.queries)
    assert len(set(result.queries)) == len(
        result.queries
    )  # All queries should be unique
