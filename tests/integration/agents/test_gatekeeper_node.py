import pytest
from deepeval import assert_test
from deepeval.metrics import ConversationalGEval
from deepeval.test_case import ConversationalTestCase, LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from integration.agents.fixtures.messages import (
    conversation_sample_2,
    conversation_sample_5,
    conversation_sample_6,
)
from integration.conftest import convert_dict_to_messages, create_mock_state


# Correctness metric for not general queries that needs planning
@pytest.fixture
def gatekeeper_correctness_metric(evaluator_model):
    return ConversationalGEval(
        name="Semantic Similarity",
        evaluation_steps=[
            """
            Evaluate whether two answers are semantically similar or convey the same meaning.
            Ensure code blocks (YAML, JavaScript, JSON, etc.) are identical in both answers without any changes.
            """,
        ],
        evaluation_params=[
            LLMTestCaseParams.EXPECTED_OUTPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.7,
        verbose_mode=True,
    )


@pytest.mark.parametrize(
    "test_description, messages, expected_answer, expected_query_forwarding",
    [  # Implicit Kubernetes/Kyma queries that should be forwarded
        (
            "cluster-scoped kyma api rules query should be forwarded",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="is something wrong with api rules?"),
            ],
            "",
            True,
        ),
        (
            "cluster-scoped kyma serverless query should be forwarded",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="is there any error in serverless?"),
            ],
            "",
            True,
        ),
        (
            "cluster-scoped kyma subscription query should be forwarded",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="is there any error in subscription?"),
            ],
            "",
            True,
        ),
        (
            "cluster-scoped kyma function query should be forwarded",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'namespace': ''}"
                ),
                HumanMessage(content="is there any error in function?"),
            ],
            "",
            True,
        ),
        (
            "pod-related issue without mentioning K8s",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_kind': 'Pod', 'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(content="My pod keeps restarting with status code 137"),
            ],
            "",
            True,
        ),
        (
            "service connectivity issue",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="I can't access my service on port 8080 even though it's running"
                ),
            ],
            "",
            True,
        ),
        (
            "ingress/api gateway issue (kyma related)",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="My API Gateway returns 503 errors when I try to access my microservice"
                ),
            ],
            "",
            True,
        ),
        (
            "volume mount issue",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="My container can't write to the mounted volume at /data"
                ),
            ],
            "",
            True,
        ),
        (
            "resource limits issue",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="I'm getting OOMKilled even though I set memory limits to 512Mi"
                ),
            ],
            "",
            True,
        ),
        (
            "configmap/secret issue",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="My application can't see the environment variables I defined in my config"
                ),
            ],
            "",
            True,
        ),
        (
            "serverless function issue (kyma related)",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="My function throws a 500 error when triggered by an event"
                ),
            ],
            "",
            True,
        ),
        (
            "networking policy issue",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="Service A can't communicate with Service B even though they're in the same namespace"
                ),
            ],
            "",
            True,
        ),
        (
            "kubernetes query for persistent volumes",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(content="What is the role of PersistentVolumes?"),
            ],
            "",
            True,
        ),
        (
            "kubernetes query for image pull backoff",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(content="What is causing the 'ImagePullBackOff' error?"),
            ],
            "",
            True,
        ),
        (
            "crd/operator issue",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="The status condition of my custom resource stays in 'Pending' state"
                ),
            ],
            "",
            True,
        ),
        (
            "api rule issue (kyma specific)",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="My API rule isn't exposing my service even though it's been created"
                ),
            ],
            "",
            True,
        ),
        (
            "certificate/tls issue",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="I'm getting certificate validation errors when accessing my service via HTTPS"
                ),
            ],
            "",
            True,
        ),
        (
            "eventing issue (kyma specific)",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="My subscription isn't receiving events from the application"
                ),
            ],
            "",
            True,
        ),  # TECHNICAL QUERIES THAT SHOULD BE FORWARDED
        (
            "Kyma resource status check",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(content="Can you check the status of my Kyma services?"),
            ],
            "",
            True,
        ),
        (
            "Kyma installation query",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'sample-ns'}"
                ),
                HumanMessage(
                    content="What's the best way to install Kyma on an existing cluster?"
                ),
            ],
            "",
            True,
        ),
        # CONVERSATION HISTORY SCENARIOS
        (
            "Query needing additional info despite history",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'default'}"
                ),
                HumanMessage(content="What is Kyma?"),
                AIMessage(
                    content="Kyma is an open-source project that extends Kubernetes with application connectivity and serverless computing capabilities."
                ),
                HumanMessage(
                    content="How do I troubleshoot a failing Kyma installation?"
                ),
            ],
            "",
            True,
        ),
        (
            "User asking to retrieve information for logs",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'kyma-system'}"
                ),
                HumanMessage(content="Can you check the logs for my Kyma function?"),
            ],
            "",
            True,
        ),
        # NON-TECHNICAL QUERIES
        (
            "Out of domain query",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'default'}"
                ),
                HumanMessage(content="What's the weather like today?"),
            ],
            "This question appears to be outside my domain of expertise. If you have any technical or Kyma related questions, I'd be happy to help.",
            False,
        ),
        (
            "Personal question",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'default'}"
                ),
                HumanMessage(content="What's your favorite color?"),
            ],
            "This question appears to be outside my domain of expertise. If you have any technical or Kyma related questions, I'd be happy to help.",
            False,
        ),
        (
            "Mixed query (part technical, part non-technical)",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'kyma-system'}"
                ),
                HumanMessage(
                    content="I'm feeling frustrated today. Can you help me debug my Kyma function?"
                ),
            ],
            "",  # Should be forwarded because of the Kyma technical component
            True,
        ),
        (
            "tests that the gatekeeper node correctly reply to greeting",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="Hi"),
            ],
            "Hello, how can I help you?",
            False,
        ),
        (
            "tests that the gatekeeper node correctly forward the query",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is problem with my deployment?"),
            ],
            "",
            True,
        ),
        (
            "tests that the gatekeeper node correctly forward the query",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="how to deploy a kyma function?"),
            ],
            "",
            True,
        ),
        (
            "tests that the gatekeeper node correctly forward the query",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="what is the status of my api"),
            ],
            "",
            True,
        ),
        (
            "tests that the gatekeeper node correctly forward the query",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="what is the status of my pod"),
            ],
            "",
            True,
        ),
        (
            "tests that the gatekeeper node decline a general non-technical query",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="What is the capital of Germany?"),
            ],
            "This question appears to be outside my domain of expertise. If you have any technical or Kyma related questions, I'd be happy to help.",
            False,
        ),
        (
            "tests that the gatekeeper node correctly answers a general programming related query",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content='Write "Hello, World!" code in Python'),
            ],
            'print("Hello, World!")',
            False,
        ),
        (
            "Query about self capabilities.",
            [
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'kyma-system'}"
                ),
                HumanMessage(
                    content="can you provide some example showcasing your problem solving capabilities"
                ),
            ],
            "I can help with various queries related to Kyma and Kubernetes, such as troubleshooting issues, "
            "understanding concepts, or deployment processes. For example, if you encounter an error while deploying "
            "a service in Kyma, I can guide you through the troubleshooting steps. If you have a specific problem or "
            "scenario in mind, feel free to share it, and I'll do my best to assist you!",
            False,
        ),
        (
            "tests that the gatekeeper node to forward user query as user explicitly ask  for recheck status",
            [
                AIMessage(
                    content="The `nginx` container in the `nginx-5dbddc77dd-t5fm2` pod is experiencing a "
                    "`CrashLoopBackOff` state. The last termination reason was `StartError`"
                    " with the message indicating a failure to create the containerd task "
                    "due to a context cancellation."
                ),
                SystemMessage(
                    content="The user query is related to: "
                    "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="Check why pod is failing"),
            ],
            "",
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_invoke_gatekeeper_node(
    test_description,
    messages,
    expected_answer,
    expected_query_forwarding,
    companion_graph,
    gatekeeper_correctness_metric,
):
    """
    Tests that the invoke_gatekeeper_node method of CompanionGraph answers general queries as expected.
    """
    # Given: a conversation state with messages
    user_query = messages[-1].content
    state = create_mock_state(messages)

    # When: the gatekeeper node's invoke_gatekeeper_node method is invoked
    actual_response = await companion_graph._invoke_gatekeeper_node(state, user_query)

    if expected_query_forwarding:
        assert actual_response.forward_query, "Query should be forwarded"

    else:
        assert (
            not actual_response.forward_query
        ), "Query should not be forwarded"  # query should not be forwarded
        # Then: we evaluate the direct response using deepeval metrics
        test_case = ConversationalTestCase(
            turns=[
                LLMTestCase(
                    input=messages[-1].content,
                    actual_output=actual_response.direct_response,
                    expected_output=expected_answer,
                )
            ]
        )
        assert_test(test_case, [gatekeeper_correctness_metric])


@pytest.mark.parametrize(
    "test_description, conversation_history, user_query, expected_answer, expected_query_forwarding",
    [
        (
            "answer the question based on the conversation history",
            conversation_sample_2,
            "what was the issue?",
            "The issue with the serverless Function `func1` in the namespace `kyma-serverless-function-no-replicas` not being ready "
            "is likely due to the configuration of `replicas: 0`, which means no pods are set to run. "
            "Additionally, if there were build issues, it could be related to the kaniko tool used for building container images, "
            "which may fail to run correctly in certain environments.",
            False,
        ),
        (
            "answer the question based on the conversation history",
            conversation_sample_5,
            "what was the cause?",
            "The cause of the Pod `pod-check` being in an error state is likely due to insufficient permissions "
            "for the service account `pod-reader-sa`. The container `kubectl-container` is trying to execute the "
            "command `kubectl get pods`, and if the service account does not have the necessary role bindings to "
            "list pods, it will result in an error, causing the container to terminate with an exit code of 1. "
            "You should verify the role and role binding for the service account to ensure it has the required permissions.",
            False,
        ),
        (
            "forward query as insufficient information in conversation history",
            conversation_sample_6,
            "how to expose it?",
            "",
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_gatekeeper_with_conversation_history(
    test_description,
    conversation_history,
    user_query,
    expected_answer,
    expected_query_forwarding,
    companion_graph,
    gatekeeper_correctness_metric,
):
    """
    Tests that the invoke_gatekeeper_node method of CompanionGraph answers general queries as expected.
    """
    # Given: a conversation state with messages
    all_messages = convert_dict_to_messages(conversation_history)
    # all_messages.append(HumanMessage(content=user_query))
    state = create_mock_state(all_messages)

    # When: the gatekeeper node's invoke_gatekeeper_node method is invoked
    result = await companion_graph._invoke_gatekeeper_node(state, user_query)

    if expected_query_forwarding:
        assert (
            result.forward_query
        ), "Query should be forwarded"  # query should be forwarded

    else:
        assert (
            not result.forward_query
        ), "Query should not be forwarded"  # query should not be forwarded
        # Then: we evaluate the direct response using deepeval metrics
        test_case = ConversationalTestCase(
            turns=[
                LLMTestCase(
                    input=user_query,
                    actual_output=result.direct_response,
                    expected_output=expected_answer,
                )
            ]
        )
        assert_test(test_case, [gatekeeper_correctness_metric])
