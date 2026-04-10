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

KYMA_CR_URI = "/apis/operator.kyma-project.io/v1beta2/kymas"


class FetchNonReadyModulesArgs(BaseModel):
    """Arguments for the fetch_non_ready_modules tool."""

    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    model_config = ConfigDict(arbitrary_types_allowed=True)


def _compact_condition(cond: dict) -> dict:
    """Extract only relevant fields from a condition."""
    return {
        "type": cond.get("type", ""),
        "status": cond.get("status", ""),
        "reason": cond.get("reason", ""),
        "message": cond.get("message", ""),
    }


def _extract_non_ready_modules(kyma_items: list[dict]) -> tuple[list[dict], int]:
    """Extract modules that are not in Ready state from Kyma CR status."""
    all_modules: list[dict] = []
    non_ready: list[dict] = []

    for kyma in kyma_items:
        status = kyma.get("status", {})
        modules = status.get("modules", [])
        all_modules.extend(modules)

        for module in modules:
            state = module.get("state", "")
            if state == "Ready":
                continue

            entry: dict = {
                "name": module.get("name", ""),
                "state": state,
                "version": module.get("version", ""),
            }

            resource = module.get("resource", {})
            if resource:
                entry["resource"] = {
                    "kind": resource.get("kind", ""),
                    "name": resource.get("name", ""),
                    "namespace": resource.get("namespace", ""),
                }

            conditions = resource.get("conditions") if resource else None
            if not conditions:
                conditions = module.get("conditions", [])
            if conditions:
                entry["conditions"] = [_compact_condition(c) for c in conditions]

            message = module.get("message", "")
            if message:
                entry["message"] = message

            non_ready.append(entry)

    return non_ready, len(all_modules)


@tool(infer_schema=False, args_schema=FetchNonReadyModulesArgs)
async def fetch_non_ready_modules(
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> dict:
    """Find Kyma modules whose status is not Ready. Use this to identify
    module-level issues such as failed installations, reconciliation errors,
    or modules stuck in a non-ready state."""
    try:
        response = await k8s_client.execute_get_api_request(KYMA_CR_URI)

        kyma_items: list[dict] = []
        if isinstance(response, dict) and "items" in response:
            kyma_items = response["items"]
        elif isinstance(response, list):
            kyma_items = response
        elif isinstance(response, dict):
            kyma_items = [response]

        non_ready, total = _extract_non_ready_modules(kyma_items)

        result: dict = {
            "total_modules": total,
            "non_ready_count": len(non_ready),
            "modules": non_ready,
        }

        result_str = json.dumps(result)
        if len(result_str) > MAX_TOOL_RESPONSE_CHARS:
            result["truncated"] = True

        return result
    except K8sClientError:
        raise
    except Exception as e:
        raise K8sClientError.from_exception(
            exception=e,
            tool_name="fetch_non_ready_modules",
        ) from e
