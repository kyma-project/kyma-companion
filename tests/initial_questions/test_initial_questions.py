from unittest.mock import Mock, patch

import pytest

from agents.common.data import Message
from initial_questions.inital_questions import InitialQuestionsHandler

KEY: str = "key"
LIST_NOT_RUNNING_PODS: str = "list_not_running_pods"
LIST_NODES_METRICS: str = "list_nodes_metrics"
LIST_K8S_WARNING_EVENTS: str = "list_k8s_warning_events"
LIST_RESOURCES: str = "list_resources"
LIST_K8S_EVENTS_FOR_RESOURCE: str = "list_k8s_events_for_resource"
GET_RESOURCE: str = "get_resource"
MOCK_DICT: dict = {KEY: "value"}


@patch(
    "initial_questions.inital_questions.InitialQuestionsHandler.__init__",
    return_value=None,
)
def test_generate_questions(mock_init):
    # The purpose of this test to verify that the generate_questions method
    # calls the chain.invoke method with the correct context.

    # Given:
    given_context = "This is a sample context with k8s data"
    expected_output = "question1\nquestion2\nquestion3"

    class MockChain:
        def invoke(self, inputs: dict):
            if inputs["context"] == given_context:
                return expected_output
            raise ValueError("context was not passed correctly")

    given_handler = InitialQuestionsHandler(model=Mock())

    # Mock the invoke method.
    given_handler.chain = MockChain()

    # When:
    result = given_handler.generate_questions(given_context)

    # Then:
    assert result == expected_output


@pytest.fixture
def mock_k8s_client():
    mock = Mock()
    mock.list_not_running_pods.return_value = [{KEY: LIST_NOT_RUNNING_PODS}, MOCK_DICT]
    mock.list_nodes_metrics.return_value = [{KEY: LIST_NODES_METRICS}, MOCK_DICT]
    mock.list_k8s_warning_events.return_value = [
        {KEY: LIST_K8S_WARNING_EVENTS},
        MOCK_DICT,
    ]
    mock.list_resources.return_value = [{KEY: LIST_RESOURCES}, MOCK_DICT]
    mock.list_k8s_events_for_resource.return_value = [
        {KEY: LIST_K8S_EVENTS_FOR_RESOURCE},
        MOCK_DICT,
    ]
    mock.get_resource.return_value = {KEY: GET_RESOURCE}
    return mock


@pytest.mark.parametrize(
    "message,expected_calls",
    [
        (
            Message(
                query="test",
                namespace="",
                resource_kind="cluster",
                resource_name="",
                resource_api_version="",
            ),
            [LIST_NOT_RUNNING_PODS, LIST_NODES_METRICS, LIST_K8S_WARNING_EVENTS],
        ),
        (
            Message(
                query="test",
                namespace="test-namespace",
                resource_kind="namespace",
                resource_name=None,
                resource_api_version=None,
            ),
            [LIST_K8S_WARNING_EVENTS],
        ),
        (
            Message(
                query="test",
                namespace="",
                resource_kind="test-kind",
                resource_name="test-name",
                resource_api_version="v1",
            ),
            [LIST_RESOURCES, LIST_K8S_EVENTS_FOR_RESOURCE],
        ),
        (
            Message(
                query="test",
                namespace="test-namespace",
                resource_kind="test-kind",
                resource_name="test-name",
                resource_api_version="test-api-version",
            ),
            [GET_RESOURCE, LIST_K8S_EVENTS_FOR_RESOURCE],
        ),
    ],
)
def test_fetch_relevant_data_from_k8s_cluster(message, expected_calls, mock_k8s_client):
    # Given:
    mock_model = Mock()
    handler = InitialQuestionsHandler(model=mock_model)

    # When:
    result = handler.fetch_relevant_data_from_k8s_cluster(message, mock_k8s_client)

    # Then:
    for call in expected_calls:
        assert call in result
