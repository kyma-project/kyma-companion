import json
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel
from pydantic.config import ConfigDict

from agents.common.constants import MAX_TOOL_RESPONSE_CHARS, MAX_WARNING_EVENTS
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError
from utils.logging import get_logger

logger = get_logger(__name__)


class FetchWarningEventsArgs(BaseModel):
    """Arguments for the fetch_warning_events tool."""

    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    model_config = ConfigDict(arbitrary_types_allowed=True)


def _compact_event(event: dict) -> dict:
    """Extract only diagnostic-relevant fields from a warning event."""
    involved = event.get("involvedObject", {})
    return {
        "object": f"{involved.get('kind', '?')}/{involved.get('name', '?')}",
        "namespace": involved.get("namespace", ""),
        "reason": event.get("reason", ""),
        "message": event.get("message", ""),
        "count": event.get("count", 1),
    }


def _group_key(event: dict) -> str:
    involved = event.get("involvedObject", {})
    return (
        f"{involved.get('kind', '')}/{involved.get('name', '')}"
        f"|{event.get('reason', '')}|{event.get('message', '')}"
    )


def _deduplicate_and_cap(events: list[dict]) -> tuple[list[dict], int]:
    """Group identical warnings, sum counts, sort by count descending, and cap."""
    groups: dict[str, dict] = {}
    for event in events:
        key = _group_key(event)
        if key in groups:
            groups[key]["count"] = groups[key].get("count", 1) + event.get("count", 1)
        else:
            groups[key] = _compact_event(event)

    sorted_events = sorted(groups.values(), key=lambda e: e.get("count", 0), reverse=True)
    return sorted_events[:MAX_WARNING_EVENTS], len(groups)


@tool(infer_schema=False, args_schema=FetchWarningEventsArgs)
def fetch_warning_events(
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> dict:
    """Fetch cluster-wide Kubernetes warning events, deduplicated and capped.
    Use this to identify recurring issues and problems across the cluster."""
    try:
        raw_events = k8s_client.list_k8s_warning_events(namespace="")
        events, total_unique = _deduplicate_and_cap(raw_events)

        result = {
            "total_raw_events": len(raw_events),
            "total_unique": total_unique,
            "returned": len(events),
            "events": events,
        }

        result_str = json.dumps(result)
        if len(result_str) > MAX_TOOL_RESPONSE_CHARS:
            while len(events) > 1 and len(json.dumps(result)) > MAX_TOOL_RESPONSE_CHARS:
                events.pop()
            result["returned"] = len(events)
            result["events"] = events
            result["truncated"] = True

        return result
    except Exception as e:
        raise K8sClientError.from_exception(
            exception=e,
            tool_name="fetch_warning_events",
        ) from e
