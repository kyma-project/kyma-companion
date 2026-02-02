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


# HTTP status codes for retry logic (already available in http.HTTPStatus, but documenting here)
# RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]  # Handled by HTTPStatus enum
