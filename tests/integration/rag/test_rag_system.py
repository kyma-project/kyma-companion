import pytest
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase

from rag.system import Query, RAGSystem


@pytest.fixture(scope="session")
def evaluation_metrics(evaluator_model):
    # TODO: enable it after the reranking is implemented
    # test the reranking of the retrieved documents
    # contextual_precision = ContextualPrecisionMetric(
    #     threshold=0.7, model=evaluator_model, include_reason=True
    # )

    # calculates how much retrieved context aligns with the expected output
    contextual_recall = ContextualRecallMetric(
        threshold=0.7, model=evaluator_model, include_reason=True
    )
    # TODO: enable it after chunking is improved.
    # Currently, H1 level chunking is used that return
    # lots of irrelevant information in the retrieved context
    # calculates how much retrieved context is relevant to the query
    # contextual_relevancy = ContextualRelevancyMetric(
    #     threshold=0.4, model=evaluator_model, include_reason=True
    # )

    answer_relevancy = AnswerRelevancyMetric(
        threshold=0.7, model=evaluator_model, include_reason=True
    )

    faithfulness = FaithfulnessMetric(
        threshold=0.7, model=evaluator_model, include_reason=True
    )
    return [
        contextual_recall,
        answer_relevancy,
        faithfulness,
    ]


@pytest.fixture(scope="session")
def rag_system(app_models):
    return RAGSystem(app_models)


@pytest.mark.parametrize(
    "input, expected_output_path",
    [
        pytest.param(
            "How to enable Istio sidecar proxy injection?",
            "integration/rag/fixtures/kyma_docs/istio/docs/user/tutorials/01-40-enable-sidecar-injection.md",
            id="How to enable Istio sidecar proxy injection?",
        ),
        pytest.param(
            "Why do I get a 'Connection reset by peer' response error?",
            "integration/rag/fixtures/kyma_docs/istio/docs/user/troubleshooting/03-20-connection-refused.md",
            id="Why do I get a Connection reset by peer error?",
        ),
        pytest.param(
            "function pod have have no sidecar proxy",
            "integration/rag/fixtures/kyma_docs/istio/docs/user/troubleshooting/03-30-istio-no-sidecar.md",
            id="Pods don't have sidecar",
        ),
        # serverless
        pytest.param(
            "How to expose a Function Using the APIRule Custom Resource?",
            "integration/rag/fixtures/kyma_docs/serverless/docs/user/tutorials/01-20-expose-function.md",
            id="How to expose a Function Using the APIRule Custom Resource?",
        ),
        pytest.param(
            "How to create a Function?",
            "integration/rag/fixtures/kyma_docs/serverless/docs/user/tutorials/01-10-create-inline-function.md",
            id="How to create a Function?",
        ),
        pytest.param(
            "want to create custom tracing spans for a function",
            "integration/rag/fixtures/kyma_docs/serverless/docs/user/tutorials/01-100-customize-function-traces.md",
            id="want to add additional traces for a function",
        ),
        pytest.param(
            "adding a new env var to a function",
            "integration/rag/fixtures/kyma_docs/serverless/docs/user/tutorials/01-120-inject-envs.md",
            id="adding a new env var to a function",
        ),
        pytest.param(
            "Serverless function pod has lots of restarts",
            "integration/rag/fixtures/kyma_docs/serverless/docs/user/troubleshooting-guides/03-50-serverless-periodically-restaring.md",
            id="Serverless function pod has lots of restarts",
        ),
        pytest.param(
            "why function build is failing?",
            "integration/rag/fixtures/kyma_docs/serverless/docs/user/troubleshooting-guides/03-40-function-build-failing-k3d.md",
            id="why function build is failing?",
        ),
        # telemetry manager
        pytest.param(
            "show how to create a trace pipeline",
            "integration/rag/fixtures/kyma_docs/telemetry-manager/docs/user/resources/04-tracepipeline.md",
            id="show how to create a trace pipeline",
        ),
        pytest.param(
            "what are the prerequisites for applications to enable logging?",
            "integration/rag/fixtures/kyma_docs/telemetry-manager/docs/user/02-logs.md",
            id="what are the prerequisites for applications to enable logging?",
        ),
        # eventing
        pytest.param(
            "some eventing messages are pending",
            "integration/rag/fixtures/kyma_docs/eventing-manager/docs/user/troubleshooting/evnt-05-fix-pending-messages.md",
            id="some eventing messages are pending",
        ),
        pytest.param(
            "what to do if event publish rate is so high?",
            "integration/rag/fixtures/kyma_docs/eventing-manager/docs/user/troubleshooting/evnt-04-free-jetstream-storage.md",
            id="what to do if event publish rate is so high?",
        ),
    ],
)
def test_rag_search(input, expected_output_path, rag_system, evaluation_metrics):
    # When
    query = Query(text=input)
    retrieved_docs = rag_system.retrieve(query)
    assert len(retrieved_docs) > 0, "No documents retrieved"

    actual_output = rag_system.generate(query, retrieved_docs)
    assert actual_output is not None, "RAG system generated no output"

    with open(expected_output_path) as file:
        expected_output = file.read()

    assert expected_output is not None, "Expected output document does not exist"

    retrieved_docs_content = [doc.page_content for doc in retrieved_docs]

    test_case = LLMTestCase(
        input=input,
        actual_output=actual_output,
        retrieval_context=retrieved_docs_content,
        expected_output=expected_output,
    )
    # assert_test(test_case, evaluation_metrics)

    results = evaluate(
        test_cases=[test_case],
        metrics=evaluation_metrics,
    )

    # Assert all metrics pass
    assert all(
        result.success for result in results.test_results
    ), "Not all metrics passed"
