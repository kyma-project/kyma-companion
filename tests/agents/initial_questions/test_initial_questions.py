from unittest.mock import Mock

import pytest

from agents.common.data import Message
from agents.initial_questions.inital_questions import InitialQuestionsAgent

KEY: str = "key"
LIST_NOT_RUNNING_PODS: str = "list_not_running_pods"
LIST_NODES_METRICS: str = "list_nodes_metrics"
LIST_K8S_WARNING_EVENTS: str = "list_k8s_warning_events"
LIST_RESOURCES: str = "list_resources"
LIST_K8S_EVENTS_FOR_RESOURCE: str = "list_k8s_events_for_resource"
GET_RESOURCE: str = "get_resource"
MOCK_DICT: dict = {KEY: "value"}

@pytest.fixture
def mock_k8s_client():
    mock = Mock()
    mock.list_not_running_pods.return_value = [{KEY: LIST_NOT_RUNNING_PODS}, MOCK_DICT]
    mock.list_nodes_metrics.return_value = [{KEY: LIST_NODES_METRICS}, MOCK_DICT]
    mock.list_k8s_warning_events.return_value = [{KEY: LIST_K8S_WARNING_EVENTS}, MOCK_DICT]
    mock.list_resources.return_value = [{KEY: LIST_RESOURCES}, MOCK_DICT]
    mock.list_k8s_events_for_resource.return_value = [{KEY: LIST_K8S_EVENTS_FOR_RESOURCE}, MOCK_DICT]
    mock.get_resource.return_value = {KEY: GET_RESOURCE}
    return mock

@pytest.mark.parametrize(
    "message,expected_calls",
    [
        (Message(query='test', 
                 namespace=None,
                 resource_kind='cluster',
                 resource_name=None,
                 resource_api_version=None),
         [LIST_NOT_RUNNING_PODS, LIST_NODES_METRICS, LIST_K8S_WARNING_EVENTS]),

        (Message(query='test',
                 namespace='test-namespace',
                 resource_kind='namespace',
                 resource_name=None,
                 resource_api_version=None),
         [LIST_K8S_WARNING_EVENTS]),

        (Message(query='test',
                 namespace=None,
                 resource_kind='test-kind',
                 resource_name=None,
                 resource_api_version=None),
         [LIST_RESOURCES, LIST_K8S_EVENTS_FOR_RESOURCE]),

        (Message(query='test',
                 namespace='test-namespace',
                 resource_kind='test-kind',
                 resource_name=None,
                 resource_api_version='test-api-version'), 
         [GET_RESOURCE, LIST_K8S_EVENTS_FOR_RESOURCE]),
    ],
)
def test_fetch_relevant_data_from_k8s_cluster(
    message,
    expected_calls,
    mock_k8s_client):
    # Arrange:
    mock_model = Mock()
    agent = InitialQuestionsAgent(model=mock_model)

    # Act:
    result = agent.fetch_relevant_data_from_k8s_cluster(message, mock_k8s_client)

    # Assert:
    for call in expected_calls:
        assert call in result
