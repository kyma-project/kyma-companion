import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.runnables import RunnableConfig

from agents.common.chunk_summarizer import ToolResponseSummarizer
from agents.common.utils import convert_string_to_object
from integration.agents.fixtures.k8_query_tool_response import (
    sample_deployment_tool_response,
    sample_pods_tool_response,
    sample_services_tool_response,
)
from integration.test_utils import BaseTestCase
from utils.settings import MAIN_MODEL_NAME


@pytest.fixture
def tool_response_summarization_metric(evaluator_model):
    return GEval(
        name="Tool Response Summarization Quality",
        model=evaluator_model,
        threshold=0.5,
        evaluation_steps=[
            "Determine whether the generated summary contains all the information found expected summary. ",
            "Do not penalize if generated summary contain more information which is not relevant to user query",
            "Verify that the summary has details relevant to the user query.",
            "Evaluate whether the summary maintains proper flow and readability when joining multiple chunk summaries.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        async_mode=False,
        verbose_mode=True,
    )


@pytest.fixture
def summarization_model(app_models):
    return app_models[MAIN_MODEL_NAME]


class TestCase(BaseTestCase):
    def __init__(
        self,
        name: str,
        tool_response: str,
        user_query: str,
        nums_of_chunks: int,
        expected_summary: str,
    ):
        super().__init__(name)
        self.tool_response = tool_response
        self.user_query = user_query
        self.nums_of_chunks = nums_of_chunks
        self.expected_summary = expected_summary


def create_test_cases():
    return [
        TestCase(
            "Should summarize pod list with status information",
            sample_pods_tool_response,
            "List all pods in the cluster and there status",
            2,
            """
        Found 2 pods in cert-manager namespace:
- cert-manager-769fdd4544-tjwwk: cert-manager controller pod, Running status, ready with 63 restarts
- cert-manager-cainjector-56ccdfdd58-rsr4w: cert-manager cainjector pod, Running status, ready with 113 restarts""",
        ),
        TestCase(
            "Should extract pod IP addresses and networking details",
            sample_pods_tool_response,
            "What are the IP addresses and networking details of the pods?",
            2,
            """
        Networking configuration:
- cert-manager-769fdd4544-tjwwk: Pod IP 100.96.1.30, Host IP 10.250.0.143, running on node ip-10-250-0-143.eu-west-1.compute.internal
- cert-manager-cainjector-56ccdfdd58-rsr4w: Pod IP 100.96.1.32, Host IP 10.250.0.143, running on same node""",
        ),
        TestCase(
            "Should identify pods with issues or high restart counts",
            sample_pods_tool_response,
            "Are there any pods with issues or high restart counts?",
            2,
            """
        Both pods show concerning restart counts indicating instability:
- cert-manager-769fdd4544-tjwwk: 63 restarts, last termination due to Error (exit code 1)
- cert-manager-cainjector-56ccdfdd58-rsr4w: 113 restarts, last termination due to Error (exit code 1)""",
        ),
        TestCase(
            "Should identify services accessible from outside cluster",
            sample_services_tool_response,
            "Which services can be accessed from outside the cluster?",
            3,
            """
        External access available through:
- istio-ingressgateway: LoadBalancer service with external
hostname a46cfa8ca2ffa4b27b140b1abe1ae362-1188520584.eu-west-1.elb.amazonaws.com,
providing HTTP (port 80) and HTTPS (port 443) access to the cluster.""",
        ),
        TestCase(
            "Should identify monitoring services in cluster",
            sample_services_tool_response,
            "Which services provide monitoring capabilities in the cluster?",
            5,
            """
        Monitoring-related services:
- cert-manager: Exposes Prometheus metrics on port 9402 (tcp-prometheus-servicemonitor)
- istiod: Provides HTTP monitoring on port 15014, with Prometheus annotations for scraping on port 15014""",
        ),
        TestCase(
            "Should list services grouped by namespace",
            sample_services_tool_response,
            "Which namespaces have services and what are they?",
            2,
            """
        Services by namespace:
- default: kubernetes (API server)
- cert-manager: cert-manager (monitoring), cert-manager-webhook (webhook)
- istio-system: istio-ingressgateway (ingress gateway), istiod (pilot/control plane)""",
        ),
        TestCase(
            "Should check deployment health status",
            sample_deployment_tool_response,
            "Are all deployments healthy?",
            2,
            """
        Both cert-manager deployments are healthy. cert-manager controller: 1/1 replicas available, status Available=True,
        last transition 2025-03-26. cert-manager-cainjector: 1/1 replicas available, status Available=True,
        last transition 2025-03-27. All conditions show successful progression and minimum availability.""",
        ),
        TestCase(
            "Should summarize deployment strategies used",
            sample_deployment_tool_response,
            "What are the deployment strategies used?",
            2,
            """
        Both deployments use RollingUpdate strategy with maxUnavailable=25% and maxSurge=25%.
        They have 10 revision history limit and 600 seconds progress deadline.
        Restart policy is Always with 30 seconds termination grace period.""",
        ),
        TestCase(
            "Should list ports exposed by deployment",
            sample_deployment_tool_response,
            "What ports are exposed by the deployment?",
            2,
            """
        cert-manager controller exposes port 9402 (http-metrics) with TCP protocol.
        It has Prometheus annotations configured: prometheus.io/scrape=true, prometheus.io/port=9402, prometheus.io/path=/metrics.""",
        ),
    ]


@pytest.mark.parametrize("test_case", create_test_cases())
@pytest.mark.asyncio
async def test_summarize_tool_response_integration(
    tool_response_summarization_metric,
    summarization_model,
    test_case: TestCase,
):
    summarizer = ToolResponseSummarizer(model=summarization_model)

    config = RunnableConfig()

    tool_response_list = convert_string_to_object(test_case.tool_response)
    generated_summary = await summarizer.summarize_tool_response(
        tool_response=tool_response_list,
        user_query=test_case.user_query,
        config=config,
        nums_of_chunks=test_case.nums_of_chunks,
    )

    llm_test_case = LLMTestCase(
        input=f"User Query: {test_case.user_query}\nExpected Summary: {test_case.expected_summary}",
        actual_output=generated_summary,
    )

    assert_test(
        llm_test_case,
        [tool_response_summarization_metric],
        f"{test_case.name}: Summarization quality should meet threshold",
    )
