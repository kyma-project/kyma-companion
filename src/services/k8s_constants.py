"""Constants and enums for Kubernetes operations.

This module defines constants to avoid magic strings throughout the codebase.
"""

from enum import Enum


class PodPhase(str, Enum):
    """Kubernetes Pod phase values.

    Reference: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-phase
    """

    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ContainerStateType(str, Enum):
    """Container state types in Kubernetes status."""

    WAITING = "waiting"
    RUNNING = "running"
    TERMINATED = "terminated"


class LogSource(str, Enum):
    """Source of pod logs - current or previous container."""

    CURRENT = "current"
    PREVIOUS = "previous"


class K8sApiFields:
    """Kubernetes API field names to avoid magic strings in dictionary access."""

    # Top-level fields
    STATUS: str = "status"
    EVENTS: str = "events"

    # Pod/Container status fields
    PHASE: str = "phase"
    CONTAINER_STATUSES: str = "containerStatuses"
    INIT_CONTAINER_STATUSES: str = "initContainerStatuses"

    # Container/State fields
    NAME: str = "name"
    STATE: str = "state"
    READY: str = "ready"
    RESTART_COUNT: str = "restartCount"
    LAST_STATE: str = "lastState"

    # State detail fields
    REASON: str = "reason"
    MESSAGE: str = "message"
    EXIT_CODE: str = "exitCode"

    # Event fields
    COUNT: str = "count"
    TYPE: str = "type"
    INVOLVED_OBJECT: str = "involvedObject"
    KIND: str = "kind"


class K8sResourceKind:
    """Kubernetes resource kinds."""

    POD: str = "Pod"
    EVENT: str = "Event"
