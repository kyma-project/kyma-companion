import pytest
from deepeval import assert_test
from deepeval.metrics import (
    ContextualRecallMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from integration.rag.datasets.eventing import cases as eventing_cases
from integration.rag.datasets.istio import cases as istio_cases
from integration.rag.datasets.serverless import cases as serverless_cases
from integration.rag.datasets.telemetry import cases as telemetry_cases
from rag.system import Query, RAGSystem


@pytest.fixture
def contextual_relevancy_metric(evaluator_model):
    return GEval(
        name="ContextualRelevancy",
        model=evaluator_model,
        threshold=0.5,
        evaluation_steps=[
            "Evaluate if the retrieved context directly addresses and is relevant to the query",
            "Check if the context contains key concepts and facts related to the query",
            "A document is relevant if it contains information that directly helps answer the query",
            "A document is considered **relevant** if it contains information that is not totally irrelevant with the query's intent.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        async_mode=False,
        verbose_mode=True,
    )


@pytest.fixture
def evaluation_metrics(evaluator_model, contextual_relevancy_metric):
    # test the reranking of the retrieved documents
    # calculates how much retrieved context aligns with the expected output
    contextual_recall = ContextualRecallMetric(threshold=0.5, model=evaluator_model, include_reason=True)

    faithfulness = FaithfulnessMetric(threshold=0.7, model=evaluator_model, include_reason=True)
    return [
        contextual_recall,
        contextual_relevancy_metric,
        faithfulness,
    ]


@pytest.fixture(scope="session")
def rag_system(app_models):
    return RAGSystem(app_models)


@pytest.mark.parametrize(
    "user_query, expected_output",
    [
        pytest.param(
            case["input"],
            case["expected_output"],
            id=case["input"],
        )
        for case in (istio_cases + serverless_cases + telemetry_cases + eventing_cases)
    ],
)
@pytest.mark.asyncio
async def test_rag_system(
    user_query,
    expected_output,
    rag_system,
    evaluation_metrics,
    caplog,
):
    import logging
    caplog.set_level(logging.INFO)

    query = Query(text=user_query)
    retrieved_docs = await rag_system.aretrieve(query, 10)
    assert len(retrieved_docs) > 0, "No documents retrieved"

    # convert the retrieved documents to array of strings
    retrieved_docs_content = [doc.page_content for doc in retrieved_docs]

    # Log retrieved documents for debugging
    print(f"\n{'='*80}")
    print(f"Query: {user_query}")
    print(f"Retrieved {len(retrieved_docs)} documents:")
    for i, doc in enumerate(retrieved_docs[:3], 1):  # Show first 3
        title = doc.metadata.get('title', 'No title')
        preview = doc.page_content[:100].replace('\n', ' ')
        print(f"  {i}. {title}")
        print(f"     Preview: {preview}...")
    if len(retrieved_docs) > 3:
        print(f"  ... and {len(retrieved_docs) - 3} more")
    print(f"{'='*80}\n")

    test_case = LLMTestCase(
        actual_output="",  # we dont evaluate any llm output
        input=user_query,
        retrieval_context=retrieved_docs_content,
        expected_output=expected_output,
    )

    # Evaluate each metric individually to provide clear failure info
    failed_metrics = []
    for metric in evaluation_metrics:
        try:
            metric_result = metric.measure(test_case)
            score = metric_result.score
            passed = score >= metric.threshold

            print(f"Metric: {metric.name}")
            print(f"  Score: {score:.3f} (threshold: {metric.threshold})")
            print(f"  Status: {'✓ PASS' if passed else '✗ FAIL'}")
            if hasattr(metric_result, 'reason') and metric_result.reason:
                print(f"  Reason: {metric_result.reason}")
            print()

            if not passed:
                failed_metrics.append({
                    'name': metric.name,
                    'score': score,
                    'threshold': metric.threshold,
                    'reason': getattr(metric_result, 'reason', 'No reason provided')
                })
        except Exception as e:
            print(f"Metric {metric.name} raised exception: {e}")
            failed_metrics.append({
                'name': metric.name,
                'score': 0.0,
                'threshold': metric.threshold,
                'reason': f'Exception: {str(e)}'
            })

    # Provide clear assertion message if any metrics failed
    if failed_metrics:
        failure_msg = f"\nRAG System Test Failed for query: '{user_query}'\n\n"
        failure_msg += f"Retrieved {len(retrieved_docs)} documents\n\n"
        failure_msg += "Failed Metrics:\n"
        for fm in failed_metrics:
            failure_msg += f"  • {fm['name']}: score={fm['score']:.3f}, threshold={fm['threshold']}\n"
            failure_msg += f"    Reason: {fm['reason']}\n"
        failure_msg += f"\nTop retrieved doc titles:\n"
        for i, doc in enumerate(retrieved_docs[:3], 1):
            title = doc.metadata.get('title', 'No title')
            failure_msg += f"  {i}. {title}\n"

        pytest.fail(failure_msg)
