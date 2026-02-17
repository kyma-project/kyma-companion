import logging
import traceback

import github_action_utils as gha_utils
import pytest
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

# Constants
MAX_DOCS_TO_PREVIEW = 3


def _print_retrieved_docs_summary(user_query: str, retrieved_docs: list) -> None:
    """Print a summary of retrieved documents for debugging."""
    print(f"\n{'=' * 80}")
    print(f"Query: {user_query}")
    print(f"Retrieved {len(retrieved_docs)} documents:")
    for i, doc in enumerate(retrieved_docs[:MAX_DOCS_TO_PREVIEW], 1):
        title = doc.metadata.get("title", "No title")
        preview = doc.page_content[:100].replace("\n", " ")
        print(f"  {i}. {title}")
        print(f"     Preview: {preview}...")
    if len(retrieved_docs) > MAX_DOCS_TO_PREVIEW:
        print(f"  ... and {len(retrieved_docs) - MAX_DOCS_TO_PREVIEW} more")
    print(f"{'=' * 80}\n")


def _evaluate_metric(metric, test_case) -> tuple[bool, dict | None]:
    """
    Evaluate a single metric.

    Returns:
        Tuple of (success, result_dict or error_dict)
        - If success=True, result_dict contains metric failure info or None if passed
        - If success=False, error_dict contains infrastructure error info
    """
    try:
        metric_result = metric.measure(test_case)
        score = metric_result.score
        passed = score >= metric.threshold

        print(f"Metric: {metric.name}")
        print(f"  Score: {score:.3f} (threshold: {metric.threshold})")
        print(f"  Status: {'✓ PASS' if passed else '✗ FAIL'}")
        if hasattr(metric_result, "reason") and metric_result.reason:
            print(f"  Reason: {metric_result.reason}")
        print()

        if not passed:
            return True, {
                "name": metric.name,
                "score": score,
                "threshold": metric.threshold,
                "reason": getattr(metric_result, "reason", "No reason provided"),
            }
        return True, None
    except Exception as e:
        # Infrastructure error
        with gha_utils.group(f"⚠️  Stack Trace: {metric.name} - {type(e).__name__}"):
            print(f"Exception: {type(e).__name__}: {str(e)}")
            traceback.print_exc()

        return False, {"metric": metric.name, "error_type": type(e).__name__, "error_msg": str(e)}


def _build_infrastructure_error_message(user_query: str, evaluation_errors: list[dict]) -> str:
    """Build error message for infrastructure failures."""
    error_msg = "\n❌ EVALUATION INFRASTRUCTURE ERROR\n\n"
    error_msg += f"Query: {user_query}\n\n"
    error_msg += "The following metrics could not be evaluated:\n"
    for err in evaluation_errors:
        error_msg += f"  • {err['metric']}: {err['error_type']}\n"
    error_msg += "\nThis indicates a problem with the evaluation system, not the test output.\n"
    error_msg += "Check the stack traces above for details.\n"
    return error_msg


def _build_quality_failure_message(user_query: str, retrieved_docs: list, failed_metrics: list[dict]) -> str:
    """Build error message for quality failures."""
    failure_msg = f"\nRAG System Test Failed for query: '{user_query}'\n\n"
    failure_msg += f"Retrieved {len(retrieved_docs)} documents\n\n"
    failure_msg += "Failed Metrics:\n"
    for fm in failed_metrics:
        failure_msg += f"  • {fm['name']}: score={fm['score']:.3f}, threshold={fm['threshold']}\n"
        failure_msg += f"    Reason: {fm['reason']}\n"
    failure_msg += "\nTop retrieved doc titles:\n"
    for i, doc in enumerate(retrieved_docs[:MAX_DOCS_TO_PREVIEW], 1):
        title = doc.metadata.get("title", "No title")
        failure_msg += f"  {i}. {title}\n"
    return failure_msg


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
    caplog.set_level(logging.INFO)

    query = Query(text=user_query)
    retrieved_docs = await rag_system.aretrieve(query, 10)
    assert len(retrieved_docs) > 0, "No documents retrieved"

    # convert the retrieved documents to array of strings
    retrieved_docs_content = [doc.page_content for doc in retrieved_docs]

    # Log retrieved documents for debugging
    _print_retrieved_docs_summary(user_query, retrieved_docs)

    test_case = LLMTestCase(
        actual_output="",  # we dont evaluate any llm output
        input=user_query,
        retrieval_context=retrieved_docs_content,
        expected_output=expected_output,
    )

    # Evaluate each metric individually to provide clear failure info
    # Separate infrastructure errors from quality failures
    evaluation_errors = []  # Infrastructure problems (evaluator crashed)
    failed_metrics = []  # Quality problems (score below threshold)

    for metric in evaluation_metrics:
        success, result = _evaluate_metric(metric, test_case)
        if success:
            if result is not None:
                failed_metrics.append(result)
        else:
            evaluation_errors.append(result)

    # Fail fast if evaluation infrastructure is broken
    if evaluation_errors:
        error_msg = _build_infrastructure_error_message(user_query, evaluation_errors)
        pytest.fail(error_msg)

    # Provide clear assertion message if any metrics failed (quality issues)
    if failed_metrics:
        failure_msg = _build_quality_failure_message(user_query, retrieved_docs, failed_metrics)
        pytest.fail(failure_msg)
