import os

import pytest
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
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
        threshold=0.5, model=evaluator_model, include_reason=True
    )
    # TODO: enable it after chunking is improved.
    # Currently, H1 level chunking is used that return
    # lots of irrelevant information in the retrieved context
    # calculates how much retrieved context is relevant to the query
    contextual_relevancy = ContextualRelevancyMetric(
        threshold=0.5, model=evaluator_model, include_reason=True
    )

    answer_relevancy = AnswerRelevancyMetric(
        threshold=0.7, model=evaluator_model, include_reason=True
    )

    faithfulness = FaithfulnessMetric(
        threshold=0.7, model=evaluator_model, include_reason=True
    )
    return [
        contextual_recall,
        contextual_relevancy,
        answer_relevancy,
        faithfulness,
    ]


@pytest.fixture(scope="session")
def rag_system(app_models):
    return RAGSystem(app_models)


@pytest.mark.parametrize(
    "user_query, expected_output_path",
    [
        pytest.param(
            "How to enable Istio sidecar proxy injection?",
            "fixtures/kyma_docs/istio/docs/user/tutorials/01-40-enable-sidecar-injection.md",
            id="How to enable Istio sidecar proxy injection?",
        ),
        pytest.param(
            "Why do I get a 'Connection reset by peer' error?",
            # "Why do I get a connection refuses error?",
            "fixtures/kyma_docs/istio/docs/user/troubleshooting/03-20-connection-refused.md",
            id="Why do I get a 'Connection reset by peer' error?",
        ),
        pytest.param(
            "how to resolve 'Connection reset by peer' error?",
            # "Why do I get a connection refuses error?",
            "fixtures/kyma_docs/istio/docs/user/troubleshooting/03-20-connection-refused.md",
            id="how to resolve 'Connection reset by peer' error?",
        ),
        pytest.param(
            "function pod have have no sidecar proxy",
            # "fixtures/kyma_docs/istio/docs/user/troubleshooting/03-30-istio-no-sidecar.md",
            "fixtures/kyma_docs/istio/docs/user/troubleshooting/no-sidecar-proxy.md",
            id="Pods don't have sidecar",
        ),
        # serverless
        pytest.param(
            "How to expose a Function Using the APIRule Custom Resource?",
            # "fixtures/kyma_docs/serverless/docs/user/tutorials/01-20-expose-function.md",
            "fixtures/kyma_docs/serverless/docs/user/tutorials/expose-function-api-rule.md",
            id="How to expose a Function Using the APIRule Custom Resource?",
        ),
        pytest.param(
            "How to create a Function?",
            "fixtures/kyma_docs/serverless/docs/user/tutorials/01-10-create-inline-function.md",
            id="How to create a Function?",
        ),
        pytest.param(
            "want to create custom tracing spans for a function",
            "fixtures/kyma_docs/serverless/docs/user/tutorials/01-100-customize-function-traces.md",
            id="want to add additional traces for a function",
        ),
        pytest.param(
            "adding a new env var to a function",
            "fixtures/kyma_docs/serverless/docs/user/tutorials/01-120-inject-envs.md",
            # "fixtures/kyma_docs/serverless/docs/user/tutorials/inject-function-env-var.md",
            id="adding a new env var to a function",
        ),
        pytest.param(
            "Serverless function pod has lots of restarts",
            "fixtures/kyma_docs/serverless/docs/user/troubleshooting-guides/03-50-serverless-periodically-restaring.md",
            id="Serverless function pod has lots of restarts",
        ),
        pytest.param(
            "why function build is failing?",
            "fixtures/kyma_docs/serverless/docs/user/troubleshooting-guides/03-40-function-build-failing-k3d.md",
            id="why function build is failing?",
        ),
        # telemetry manager
        pytest.param(
            "show how to create a trace pipeline",
            "fixtures/kyma_docs/telemetry-manager/docs/user/creating-trace-pipeline.md",
            id="show how to create a trace pipeline",
        ),
        # TODO: enable it after indexing is improved. Currently it is failing.
        # "fixtures/kyma_docs/telemetry-manager/docs/user/02-logs.md"
        pytest.param(
            "what are the prerequisites for Kyma application to enable logging?",
            "fixtures/kyma_docs/telemetry-manager/docs/user/app-log-prerequisites.md",
            id="what are the prerequisites for applications to enable logging?",
        ),
        pytest.param(
            "why there is no logs in the backend?",
            "fixtures/kyma_docs/telemetry-manager/docs/user/no-logs.md",
            id="why there is no logs in the backend?",
        ),
        # # eventing
        # "fixtures/kyma_docs/eventing-manager/docs/user/troubleshooting/evnt-05-fix-pending-messages.md",
        pytest.param(
            "some eventing messages are pending in the stream",
            "fixtures/kyma_docs/eventing-manager/docs/user/troubleshooting/pending-events.md",
            id="some eventing messages are pending",
        ),
        # "fixtures/kyma_docs/eventing-manager/docs/user/troubleshooting/evnt-04-free-jetstream-storage.md",
        pytest.param(
            "what to do if event publish rate is so high?",
            "fixtures/kyma_docs/eventing-manager/docs/user/troubleshooting/high-event-rate.md",
            id="what to do if event publish rate is so high?",
        ),
    ],
)
@pytest.mark.asyncio
async def test_rag_search(
    user_query, expected_output_path, rag_system, evaluation_metrics
):
    # Given: the path to the RAG directory
    rag_dir = os.path.dirname(os.path.abspath(__file__))

    # When: the documents are retrieved and the output is generated
    query = Query(text=user_query)
    retrieved_docs = await rag_system.aretrieve(query)
    assert len(retrieved_docs) > 0, "No documents retrieved"

    actual_output = await rag_system.agenerate(query, retrieved_docs)
    assert actual_output is not None, "RAG system generated no output"
    # Then
    # the expected output document exists
    with open(os.path.join(rag_dir, expected_output_path)) as file:
        expected_output = file.read()
    assert expected_output is not None, "Expected output document does not exist"
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
