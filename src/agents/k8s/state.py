import operator
from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage
from langchain_core.pydantic_v1 import BaseModel
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep

from agents.common.state import SubTask
from agents.k8s.constants import K8S_CLIENT
from services.k8s import IK8sClient


class KubernetesAgentState(BaseModel):
    """The state of the Kubernetes agent."""

    # Fields shared with the parent graph (Kyma graph).
    messages: Annotated[Sequence[BaseMessage], add_messages]
    subtasks: list[SubTask] | None = []
    k8s_client: IK8sClient

    # Subgraph private fields
    my_task: SubTask | None = None
    is_last_step: IsLastStep

    class Config:
        arbitrary_types_allowed = True
        fields = {K8S_CLIENT: {"exclude": True}}
