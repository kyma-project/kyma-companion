import os

import pytest
from deepeval import assert_test
from deepeval.metrics.contextual_precision.contextual_precision import (
    ContextualPrecisionMetric,
)
from deepeval.test_case.llm_test_case import LLMTestCase
from langchain_core.documents import Document

from rag.reranker.reranker import (
    LLMReranker,
    document_to_str,
    format_documents,
    format_queries,
)
from utils.settings import MAIN_MODEL_MINI_NAME


@pytest.fixture
def contextual_precision(evaluator_model):
    def callback(threshold: float):
        contextual_precision = ContextualPrecisionMetric(
            threshold=threshold,
            model=evaluator_model,
            include_reason=True,
        )
        return contextual_precision

    return callback


@pytest.fixture(scope="session")
def llm_reranker(app_models):
    return LLMReranker(app_models[MAIN_MODEL_MINI_NAME])


@pytest.mark.parametrize(
    "name, given_docs_path, given_queries, given_limit, expected_docs_paths, threshold",
    [
        # Eventing
        (
            "some eventing messages are pending in the stream",
            "datasets/reranker/messages-pending-in-stream",
            ["some eventing messages are pending in the stream"],
            4,
            [
                "datasets/reranker/messages-pending-in-stream/03_published_events_are_pending_in_the_stream.md",
            ],
            0.5,
        ),
        (
            "what to do if event publish rate is too high for NATS?",
            "datasets/reranker/event-publish-rate-too-high-nats",
            ["what to do if event publish rate is too high for NATS?"],
            4,
            [
                "datasets/reranker/event-publish-rate-too-high-nats/00_eventing_backend_stopped_receiving_events_due_to_full_storage.md",
            ],
            0.5,
        ),
        # Istio
        (
            "How to enable Istio sidecar proxy injection?",
            "datasets/reranker/enable-istio-sidecar-proxy-injection",
            [
                "How to enable Istio sidecar proxy injection?",
            ],
            4,
            [
                "datasets/reranker/enable-istio-sidecar-proxy-injection/00_enable_istio_sidecar_proxy_injection.md",
            ],
            0.5,
        ),
        (
            "why an Istio sidecar is not injected to a pod?",
            "datasets/reranker/istio-sidecar-not-injected-to-pod",
            [
                "why an Istio sidecar is not injected to a pod?",
            ],
            4,
            [
                "datasets/reranker/istio-sidecar-not-injected-to-pod/01_istio_sidecar_proxy_injection_issues_cause.md",
            ],
            0.5,
        ),
        (
            "Why do I get a 'Connection reset by peer' error?",
            "datasets/reranker/connection-reset-by-peer-error",
            [
                "Why do I get a 'Connection reset by peer' error?",
            ],
            4,
            [
                "datasets/reranker/connection-reset-by-peer-error/05_connection_refused_errors.md",
            ],
            0.5,
        ),
        (
            "function pod have no sidecar proxy",
            "datasets/reranker/function-pod-have-no-sidecar-proxy",
            [
                "function pod have no sidecar proxy",
            ],
            4,
            [
                "datasets/reranker/function-pod-have-no-sidecar-proxy/02_istio_sidecar_proxy_injection_issues_solution.md",
            ],
            0.5,
        ),
        # Serverless
        (
            "why function build is failing?",
            "datasets/reranker/function-build-failing",
            [
                "why function build is failing?",
            ],
            4,
            [
                "datasets/reranker/function-build-failing/03_failure_to_build_functions.md",
            ],
            0.5,
        ),
        (
            "How to expose a Function Using the APIRule Custom Resource?",
            "datasets/reranker/expose-function-using-apirule",
            [
                "How to expose a Function Using the APIRule Custom Resource?",
            ],
            4,
            [
                "datasets/reranker/expose-function-using-apirule/01_expose_a_function_using_the_apirule_custom_resource_steps.md",
                "datasets/reranker/expose-function-using-apirule/02_expose_a_function_using_the_apirule_custom_resource.md",
            ],
            0.5,
        ),
        (
            "How to create a Function?",
            "datasets/reranker/how-to-create-function",
            [
                "How to create a Function?",
            ],
            4,
            [
                "datasets/reranker/how-to-create-function/01_create_and_modify_an_inline_function_steps.md",
            ],
            0.5,
        ),
        (
            "want to create custom tracing spans for a function",
            "datasets/reranker/create-custom-tracing-spans-for-function",
            [
                "want to create custom tracing spans for a function",
            ],
            4,
            [
                "datasets/reranker/create-custom-tracing-spans-for-function/00_customize_function_traces.md",
            ],
            0.5,
        ),
        (
            "adding a new env var to a function",
            "datasets/reranker/add-env-var-to-function",
            [
                "adding a new env var to a function",
            ],
            4,
            [
                "datasets/reranker/add-env-var-to-function/01_inject_environment_variables.md",
            ],
            0.5,
        ),
        (
            "Serverless function pod has lots of restarts",
            "datasets/reranker/serverless-function-pod-restarts",
            [
                "Serverless function pod has lots of restarts",
            ],
            4,
            [
                "datasets/reranker/serverless-function-pod-restarts/02_serverless_periodically_restarting.md",
            ],
            0.5,
        ),
        # Telemetry
        (
            "show how to create a trace pipeline",
            "datasets/reranker/show-how-to-create-trace-pipeline",
            [
                "show how to create a trace pipeline",
            ],
            4,
            [
                "datasets/reranker/show-how-to-create-trace-pipeline/03_traces_setting_up_a_tracepipeline_1_create_a_tracepipeline.md",
            ],
            0.5,
        ),
        (
            "what are the prerequisites for Kyma application to enable logging?",
            "datasets/reranker/prerequisites-to-enable-logging",
            [
                "what are the prerequisites for Kyma application to enable logging?",
            ],
            4,
            [
                "datasets/reranker/prerequisites-to-enable-logging/03_application_logs_prerequisites.md",
            ],
            0.5,
        ),
        (
            "why there is no logs in the backend?",
            "datasets/reranker/no-logs-in-backend",
            [
                "why there is no logs in the backend?",
            ],
            4,
            [
                "datasets/reranker/no-logs-in-backend/00_application_logs_troubleshooting.md",
                "datasets/reranker/no-logs-in-backend/01_application_logs_operations.md",
            ],
            0.5,
        ),
    ],
)
@pytest.mark.asyncio
async def test_chain_ainvoke(
    name,
    given_docs_path,
    given_queries,
    given_limit,
    expected_docs_paths,
    llm_reranker,
    threshold,
    contextual_precision,
):
    """
    This test ensures that the reranker chain (prompt and output) is working as expected.
    :param name: name of the test.
    :param given_docs_path: path to given documents.
    :param given_queries: list of queries.
    :param given_limit: limit of documents to return.
    :param expected_docs_paths: list of paths to expected documents.
    :param llm_reranker: LLMReranker instance.
    :param contextual_precision: contextual_precision metric.
    """

    # Prepare
    base_path = os.path.dirname(os.path.abspath(__file__))
    given_docs_full_path = os.path.join(base_path, given_docs_path)
    expected_docs_full_paths = [
        str(os.path.join(base_path, path)) for path in expected_docs_paths
    ]

    # Given
    given_docs = load_docs_in_path(given_docs_full_path, ".md")
    expected_docs = load_docs(expected_docs_full_paths)

    # When
    actual_docs = await llm_reranker._chain_ainvoke(
        docs=given_docs,
        queries=given_queries,
        limit=given_limit,
    )

    # Then
    tc_input = format_queries(given_queries)
    tc_actual_output = format_documents(actual_docs)
    tc_retrieval_context = [document_to_str(doc) for doc in actual_docs]
    tc_expected_output = format_documents(expected_docs)
    test_case = LLMTestCase(
        input=tc_input,
        actual_output=tc_actual_output,
        retrieval_context=tc_retrieval_context,
        expected_output=tc_expected_output,
    )

    # Report the test summary for debugging purposes.
    report_test_summary(given_queries, given_docs, actual_docs, expected_docs)

    actual_docs_titles = get_docs_titles(actual_docs)
    expected_docs_titles = get_docs_titles(expected_docs)
    # Assert that the expected documents are in the actual list of documents.
    assert set(expected_docs_titles).issubset(
        set(actual_docs_titles)
    ), "Expected documents not found in actual output"
    # Assert that the contextual precision is above the threshold.
    assert_test(test_case, [contextual_precision(threshold)])


def load_docs_in_path(path: str, extension: str, sort: bool = True) -> list[Document]:
    paths = [
        os.path.join(dp, f)
        for dp, dn, filenames in os.walk(path)
        for f in filenames
        if os.path.splitext(f)[1] == extension
    ]

    if sort:
        paths = sorted(paths)

    return load_docs(paths)


def load_docs(paths: list[str]) -> list[Document]:
    docs = []
    for path in paths:
        with open(path) as file:
            content = file.read()
            docs.append(Document(page_content=content))
    return docs


def report_test_summary(given_queries, given_docs, actual_docs, expected_docs):
    print(
        """
+----------------------------------------------+
|                 TEST SUMMARY                 |
+----------------------------------------------+
"""
    )
    report_queries("Queries", given_queries)
    report_docs("Given docs", given_docs)
    report_docs("Actual docs", actual_docs)
    report_docs("Expected docs", expected_docs)
    print(
        "Number of actual and expected documents are {result}.".format(
            result=("equal" if len(actual_docs) == len(expected_docs) else "not equal")
        )
    )


def report_queries(prefix, queries):
    print(f"{prefix} ({len(queries):02d}):\n- {"\n- ".join(queries)}\n")


def get_docs_titles(docs):
    return [doc.page_content.split("\n")[0].strip() for doc in docs]


def report_docs(prefix, docs):
    docs_list = get_docs_titles(docs)
    print(f"{prefix} ({len(docs_list):02d}):\n- {"\n- ".join(docs_list)}\n")
