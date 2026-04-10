import json
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel
from pydantic.config import ConfigDict

from agents.common.constants import MAX_TOOL_RESPONSE_CHARS
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError
from utils.logging import get_logger

logger = get_logger(__name__)

DIAGNOSTIC_CONDITIONS = {"Ready", "MemoryPressure", "DiskPressure", "PIDPressure", "NetworkUnavailable"}


class FetchNodeResourcesArgs(BaseModel):
    """Arguments for the fetch_node_resources tool."""

    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    model_config = ConfigDict(arbitrary_types_allowed=True)


def _compact_node(node: dict) -> dict:
    """Extract only diagnostic-relevant fields from a node object."""
    metadata = node.get("metadata", {})
    status = node.get("status", {})
    labels = metadata.get("labels", {})

    capacity = status.get("capacity", {})
    allocatable = status.get("allocatable", {})

    conditions = []
    for cond in status.get("conditions", []):
        if cond.get("type") in DIAGNOSTIC_CONDITIONS:
            conditions.append({
                "type": cond["type"],
                "status": cond.get("status", ""),
                "reason": cond.get("reason", ""),
                "message": cond.get("message", ""),
            })

    node_info = status.get("nodeInfo", {})

    return {
        "name": metadata.get("name", ""),
        "topology": {
            "region": labels.get("topology.kubernetes.io/region", ""),
            "zone": labels.get("topology.kubernetes.io/zone", ""),
        },
        "capacity": {
            "cpu": capacity.get("cpu", ""),
            "memory": capacity.get("memory", ""),
            "pods": capacity.get("pods", ""),
        },
        "allocatable": {
            "cpu": allocatable.get("cpu", ""),
            "memory": allocatable.get("memory", ""),
            "pods": allocatable.get("pods", ""),
        },
        "conditions": conditions,
        "kubeletVersion": node_info.get("kubeletVersion", ""),
        "containerRuntime": node_info.get("containerRuntimeVersion", ""),
        "osImage": node_info.get("osImage", ""),
    }


def _compact_metrics(metric: dict) -> dict:
    """Extract usage data from a node metrics object."""
    return {
        "name": metric.get("metadata", {}).get("name", ""),
        "cpu": metric.get("usage", {}).get("cpu", ""),
        "memory": metric.get("usage", {}).get("memory", ""),
    }


def _merge_nodes_and_metrics(nodes: list[dict], metrics: list[dict]) -> list[dict]:
    """Merge compacted node info with compacted metrics by node name."""
    metrics_by_name = {m["name"]: m for m in metrics}
    result = []
    for node in nodes:
        entry = dict(node)
        metric = metrics_by_name.get(node["name"])
        if metric:
            entry["usage"] = {"cpu": metric["cpu"], "memory": metric["memory"]}
        else:
            entry["usage"] = {"cpu": "N/A", "memory": "N/A"}
        result.append(entry)
    return result


@tool(infer_schema=False, args_schema=FetchNodeResourcesArgs)
async def fetch_node_resources(
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> dict:
    """Fetch node resource info including capacity, allocatable resources, conditions,
    and actual usage metrics for all cluster nodes. Use this to identify resource
    pressure, unhealthy nodes, or capacity issues."""
    try:
        nodes_response = await k8s_client.execute_get_api_request("/api/v1/nodes")

        raw_nodes: list[dict] = []
        if isinstance(nodes_response, dict) and "items" in nodes_response:
            raw_nodes = nodes_response["items"]
        elif isinstance(nodes_response, list):
            raw_nodes = nodes_response

        compacted_nodes = [_compact_node(n) for n in raw_nodes]

        compacted_metrics: list[dict] = []
        try:
            raw_metrics = await k8s_client.list_nodes_metrics()
            compacted_metrics = [_compact_metrics(m) for m in raw_metrics]
        except Exception:
            logger.warning("Failed to fetch node metrics, usage data will be N/A")

        merged = _merge_nodes_and_metrics(compacted_nodes, compacted_metrics)

        result: dict = {
            "total_nodes": len(merged),
            "nodes": merged,
        }

        result_str = json.dumps(result)
        if len(result_str) > MAX_TOOL_RESPONSE_CHARS:
            result["truncated"] = True
            result["note"] = f"Output truncated. Showing {len(merged)} nodes."

        return result
    except K8sClientError:
        raise
    except Exception as e:
        raise K8sClientError.from_exception(
            exception=e,
            tool_name="fetch_node_resources",
        ) from e
