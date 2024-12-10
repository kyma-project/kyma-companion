import pytest
from deepeval import evaluate
from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase

from integration.rag.datasets.eventing import cases as eventing_cases
from integration.rag.datasets.istio import cases as istio_cases
from integration.rag.datasets.serverless import cases as serverless_cases
from integration.rag.datasets.telemetry import cases as telemetry_cases
from rag.system import Query, RAGSystem


@pytest.fixture
def evaluation_metrics(evaluator_model, answer_relevancy_metric):
    # test the reranking of the retrieved documents
    contextual_precision = ContextualPrecisionMetric(
        threshold=0.5, model=evaluator_model, include_reason=True
    )
    # calculates how much retrieved context aligns with the expected output
    contextual_recall = ContextualRecallMetric(
        threshold=0.5, model=evaluator_model, include_reason=True
    )
    # calculates how much retrieved context is relevant to the query
    contextual_relevancy = ContextualRelevancyMetric(
        threshold=0.5, model=evaluator_model, include_reason=True
    )

    faithfulness = FaithfulnessMetric(
        threshold=0.7, model=evaluator_model, include_reason=True
    )
    return [
        contextual_precision,
        contextual_recall,
        contextual_relevancy,
        answer_relevancy_metric,
        faithfulness,
    ]


@pytest.fixture(scope="session")
def rag_system(app_models):
    return RAGSystem(app_models)


class TestRagSearch:
    """Test RAG search for Kyma documentation."""

    @pytest.mark.parametrize(
        "user_query, expected_output",
        [
            pytest.param(
                case["input"],
                case["expected_output"],
                id=case["input"],
            )
            for case in istio_cases
        ],
    )
    @pytest.mark.asyncio
    async def test_istio_queries(
        self, user_query, expected_output, rag_system, evaluation_metrics
    ):
        await execute_tests(user_query, expected_output, rag_system, evaluation_metrics)

    @pytest.mark.parametrize(
        "user_query, expected_output, answer_relevancy_threshold",
        [
            pytest.param(
                case["input"],
                case["expected_output"],
                case["answer_relevancy_threshold"],
                id=case["input"],
            )
            for case in serverless_cases
        ],
    )
    @pytest.mark.asyncio
    async def test_serverless_queries(
        self,
        user_query,
        expected_output,
        answer_relevancy_threshold,
        rag_system,
        evaluation_metrics,
    ):
        # Update the answer relevancy metric threshold
        # we need this because the answer relevancy metric is not always above 0.7
        for metric in evaluation_metrics:
            if metric.__class__.__name__ == "AnswerRelevancyMetric":
                metric.threshold = answer_relevancy_threshold

        await execute_tests(user_query, expected_output, rag_system, evaluation_metrics)

    @pytest.mark.parametrize(
        "user_query, expected_output",
        [
            # telemetry manager
            pytest.param(
                case["input"],
                case["expected_output"],
                id=case["input"],
            )
            for case in telemetry_cases
        ],
    )
    @pytest.mark.asyncio
    async def test_telemetry_queries(
        self, user_query, expected_output, rag_system, evaluation_metrics
    ):
        await execute_tests(user_query, expected_output, rag_system, evaluation_metrics)

    @pytest.mark.parametrize(
        "user_query, expected_output",
        [
            # "fixtures/kyma_docs/eventing-manager/docs/user/troubleshooting/evnt-05-fix-pending-messages.md",
            pytest.param(
                case["input"],
                case["expected_output"],
                id=case["input"],
            )
            for case in eventing_cases
        ],
    )
    @pytest.mark.asyncio
    async def test_eventing_queries(
        self, user_query, expected_output, rag_system, evaluation_metrics
    ):
        await execute_tests(user_query, expected_output, rag_system, evaluation_metrics)


async def execute_tests(user_query, expected_output, rag_system, evaluation_metrics):
    query = Query(text=user_query)
    retrieved_docs = await rag_system.aretrieve(query, 10)
    assert len(retrieved_docs) > 0, "No documents retrieved"

    actual_output = await rag_system.agenerate(query, retrieved_docs)
    assert actual_output is not None, "RAG system generated no output"

    # convert the retrieved documents to array of strings
    retrieved_docs_content = [doc.page_content for doc in retrieved_docs]

    test_case = LLMTestCase(
        input=user_query,
        actual_output=actual_output,
        retrieval_context=retrieved_docs_content,
        expected_output=expected_output,
    )
    # evaluate the test case using deepeval metrics
    results = evaluate(
        test_cases=[test_case],
        metrics=evaluation_metrics,
    )

    # Assert all metrics pass
    assert all(
        result.success for result in results.test_results
    ), "Not all metrics passed"
