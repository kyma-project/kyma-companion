import asyncio
import uuid
from textwrap import dedent

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.common.utils import get_current_day_timestamps_utc
from integration.agents.test_common_node import create_mock_state
from services.langfuse import LangfuseService
from utils.common import MetricsResponse

LANGFUSE_MAX_ATTEMPTS = 10
RETRY_WAIT_TIME = 20


@pytest.fixture
def langfuse_service():
    return LangfuseService()


@pytest.mark.asyncio
async def test_get_daily_metrics(langfuse_service):
    # Define the timestamps for the test
    to_timestamp, from_timestamp = get_current_day_timestamps_utc()

    # Call the method to test
    response = await langfuse_service.get_daily_metrics(from_timestamp, to_timestamp)

    # Assert that the response is not None and is of the correct type
    assert response is not None
    assert isinstance(response, MetricsResponse)


@pytest.mark.asyncio
async def test_get_total_token_usage(langfuse_service):
    # Define the timestamps for the test
    to_timestamp, from_timestamp = get_current_day_timestamps_utc()

    total_token_usage = await langfuse_service.get_total_token_usage(
        from_timestamp, to_timestamp
    )

    # Assert that the total token usage is an integer
    assert isinstance(total_token_usage, int)
    assert total_token_usage >= 0


@pytest.mark.parametrize(
    "messages , input_token_count",
    [
        # Messages for input
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(
                    content="what are the types of a k8s service? what is a kyma function?"
                ),
                AIMessage(
                    name="KubernetesAgent",
                    content=dedent(
                        """
                    Kubernetes services can be of several types, each serving a different purpose. The main types of
                    Kubernetes services are:
                    1. **ClusterIP**: Exposes the service on a cluster-internal IP. This type makes the service only
                    reachable from within the cluster. It is the default type of service.
                    2. **NodePort**: Exposes the service on each Node’s IP at a static port (the NodePort). A ClusterIP
                    service, to which the NodePort service routes, is automatically created. You’ll be able to contact the
                    NodePort service, from outside the cluster, by requesting `<NodeIP>:<NodePort>`.
                    3. **LoadBalancer**: Exposes the service externally using a cloud provider’s load balancer. NodePort and
                    ClusterIP services, to which the external load balancer routes, are automatically created.
                    4. **ExternalName**: Maps the service to the contents of the `externalName` field (e.g.,
                    `foo.bar.example.com`), by returning a CNAME record with its value. No proxying of any kind is set up.
                    These types allow Kubernetes to offer different ways to expose applications depending on the use case
                    and the environment in which the cluster is running.
                    """
                    ),
                ),
                AIMessage(
                    name="KymaAgent",
                    content=dedent(
                        """
                    A Kyma function is a lightweight, serverless function that runs in the Kyma environment. It allows you
                    to execute custom business logic in response to events or HTTP requests. Functions are typically written
                    in JavaScript or TypeScript and can be deployed easily within the Kyma ecosystem.
                    Key features of Kyma functions include:
                    1. **Event-Driven**: Functions can be triggered by various events, such as HTTP requests, messages from
                    a message broker, or other events in the Kyma environment.
                    2. **Scalability**: They automatically scale based on demand, allowing you to handle varying loads
                    without manual intervention.
                    3. **Integration**: Functions can easily integrate with other services and components in the Kyma
                    ecosystem, such as APIs, databases, and external services.
                    4. **Isolation**: Each function runs in its own isolated environment, ensuring that they do not
                    interfere with each other.
                    Overall, Kyma functions are a powerful way to extend the capabilities of your applications in a
                    cloud-native environment.
                    5. **Easy Deployment**: Functions can be deployed using the Kyma console, CLI, or CI/CD pipelines,
                    making it straightforward to manage and update them.
                    """
                    ),
                ),
            ],
            842,
        )
    ],
)
@pytest.mark.asyncio
async def test_langfuse_end_to_end(
    messages,
    input_token_count,
    companion_graph,
    semantic_similarity_metric,
    langfuse_service,
):
    # Conversation state with messages
    state = create_mock_state(messages)

    # Generate a random UUID
    random_guid = uuid.uuid4()
    cluster_id = str(random_guid).replace("-", "")

    config_data = {
        "configurable": {
            "thread_id": "test_conversation_id",
        },
        "callbacks": [langfuse_service.handler],
        "tags": [cluster_id],
    }

    #  Finalizer response chain
    final_response_chain = companion_graph.supervisor_agent._final_response_chain(state)

    # Invoke the RunnableSequence with the config
    await final_response_chain.ainvoke(
        input={"messages": state.messages}, config=config_data
    )

    # Define the timestamps for the getting trace from langfuse
    from_timestamp, to_timestamp = get_current_day_timestamps_utc()

    # Poll Langfuse until the data is saved
    max_attempts = LANGFUSE_MAX_ATTEMPTS
    attempt = 0
    total_token_count = 0

    while attempt < max_attempts:
        total_token_count = await langfuse_service.get_total_token_usage(
            from_timestamp, to_timestamp, tags=cluster_id
        )
        if total_token_count != 0:
            break
        attempt += 1
        await asyncio.sleep(RETRY_WAIT_TIME)  # Wait before retrying

    assert total_token_count >= input_token_count
