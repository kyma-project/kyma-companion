from unittest.mock import AsyncMock, Mock, patch

import pytest

from agents.common.data import Message
from agents.k8s.tools.query import k8s_overview_query_tool, k8s_query_tool
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError


def sample_k8s_secret():
    return {
        "kind": "Secret",
        "apiVersion": "v1",
        "metadata": {
            "name": "my-secret",
        },
        "data": {
            "config": "this is a test config",
        },
    }


@pytest.mark.parametrize(
    "given_uri, given_object, given_exception, expected_object, expected_error",
    [
        (
            "v1/secret/my-secret",
            sample_k8s_secret(),
            None,
            sample_k8s_secret(),
            None,
        ),
        (
            "v1/secret/my-secret",
            sample_k8s_secret(),
            Exception("dummy error 1"),
            None,
            K8sClientError(
                message="dummy error 1",
                status_code=500,
                uri="v1/secret/my-secret",
            ),
        ),
        (
            "v1/secret/my-secret",
            None,
            K8sClientError(
                message="Invalid result type: <class 'str'>",
                status_code=500,
                uri="v1/secret/my-secret",
            ),
            None,
            K8sClientError(
                message="Invalid result type: <class 'str'>",
                status_code=500,
                uri="v1/secret/my-secret",
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_k8s_query_tool(given_uri, given_object, given_exception, expected_object, expected_error):
    k8s_client = AsyncMock(spec=IK8sClient)
    if given_exception:
        k8s_client.execute_get_api_request.side_effect = given_exception
    else:
        k8s_client.execute_get_api_request.return_value = given_object

    if expected_error:
        with pytest.raises(K8sClientError):
            await k8s_query_tool.ainvoke({"uri": given_uri, "k8s_client": k8s_client})
    else:
        result = await k8s_query_tool.ainvoke({"uri": given_uri, "k8s_client": k8s_client})
        k8s_client.execute_get_api_request.assert_called_once_with(given_uri)
        assert result == expected_object


def sample_cluster_overview():
    return {"nodes": 3, "namespaces": ["default", "kube-system"], "version": "v1.25.0"}


def sample_namespace_overview():
    return {"pods": 5, "services": 2, "deployments": 3}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "given_namespace, given_resource_kind, given_result, given_exception, expected_result, expected_error",
    [
        (
            "",
            "cluster",
            sample_cluster_overview(),
            None,
            sample_cluster_overview(),
            None,
        ),
        (
            "default",
            "namespace",
            sample_namespace_overview(),
            None,
            sample_namespace_overview(),
            None,
        ),
        (
            "default",
            "namespace",
            None,
            Exception("cluster unavailable"),
            None,
            K8sClientError(message="cluster unavailable", status_code=500),
        ),
        (
            "default",
            "invalid_kind",
            None,
            Exception("Unsupported resource kind: invalid_kind"),
            None,
            K8sClientError(message="Unsupported resource kind: invalid_kind", status_code=500),
        ),
    ],
)
@patch("agents.k8s.tools.query.get_relevant_context_from_k8s_cluster")
async def test_k8s_overview_query_tool(
    mock_get_context,
    given_namespace,
    given_resource_kind,
    given_result,
    given_exception,
    expected_result,
    expected_error,
):
    k8s_client = Mock(spec=IK8sClient)

    if given_exception:
        mock_get_context.side_effect = given_exception
    else:
        mock_get_context.return_value = given_result

    if expected_error:
        with pytest.raises(K8sClientError):
            await k8s_overview_query_tool.ainvoke(
                {
                    "namespace": given_namespace,
                    "resource_kind": given_resource_kind,
                    "k8s_client": k8s_client,
                }
            )
    else:
        result = await k8s_overview_query_tool.ainvoke(
            {
                "namespace": given_namespace,
                "resource_kind": given_resource_kind,
                "k8s_client": k8s_client,
            }
        )
        assert result == expected_result

    mock_get_context.assert_called_once_with(
        Message(
            resource_kind=given_resource_kind,
            namespace=given_namespace,
            query="",
            resource_api_version="",
            resource_name="",
        ),
        k8s_client,
    )
