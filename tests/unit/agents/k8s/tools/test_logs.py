import json
from unittest.mock import AsyncMock

import pytest

from agents.k8s.tools.logs import POD_LOGS_TAIL_LINES_LIMIT, fetch_pod_logs_tool
from services.k8s import IK8sClient


@pytest.mark.parametrize(
    "given_name, given_namespace, given_container_name, given_error, expected_logs_dict, expected_error",
    [
        (
            "my-pod",
            "my-namespace",
            "my-container",
            None,
            {
                "logs": {
                    "current_container": "line 1\nline 2\nline 3",
                    "previously_terminated_container": "Not available (container has not been restarted)",
                },
                "diagnostic_context": None,
                "status_code": 200,
            },
            None,
        ),
        (
            "my-pod",
            "my-namespace",
            "my-container",
            Exception("dummy error 1"),
            None,
            Exception(
                "Error: failed executing fetch_pod_logs_tool, "
                "raised the following error: dummy error 1\n Please fix your mistakes."
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_fetch_pod_logs_tool(
    given_name,
    given_namespace,
    given_container_name,
    given_error,
    expected_logs_dict,
    expected_error,
):
    k8s_client = AsyncMock(spec=IK8sClient)
    if given_error:
        k8s_client.fetch_pod_logs.side_effect = given_error
    else:
        from services.k8s_models import PodLogs, PodLogsResult

        k8s_client.fetch_pod_logs.return_value = PodLogsResult(
            logs=PodLogs(
                current_container=expected_logs_dict["logs"]["current_container"],
                previously_terminated_container=expected_logs_dict["logs"]["previously_terminated_container"],
            ),
            diagnostic_context=expected_logs_dict["diagnostic_context"],
            status_code=expected_logs_dict["status_code"],
        )

    if given_error:
        from utils.exceptions import K8sClientError

        with pytest.raises(K8sClientError):
            await fetch_pod_logs_tool.ainvoke(
                {
                    "name": given_name,
                    "namespace": given_namespace,
                    "container_name": given_container_name,
                    "k8s_client": k8s_client,
                }
            )
    else:
        result = await fetch_pod_logs_tool.ainvoke(
            {
                "name": given_name,
                "namespace": given_namespace,
                "container_name": given_container_name,
                "k8s_client": k8s_client,
            }
        )
        k8s_client.fetch_pod_logs.assert_called_once_with(
            given_name,
            given_namespace,
            given_container_name,
            POD_LOGS_TAIL_LINES_LIMIT,
        )
        got_obj = result if isinstance(result, dict) else json.loads(result)
        assert got_obj == expected_logs_dict
