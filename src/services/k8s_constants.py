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


class ContainerStateReason(str, Enum):
    """Common reasons for container states.

    Note: These are not exhaustive - Kubernetes can have custom reasons.
    These are the most common ones we handle in our code.
    """

    # Waiting state reasons
    CRASH_LOOP_BACK_OFF = "CrashLoopBackOff"
    IMAGE_PULL_BACK_OFF = "ImagePullBackOff"
    ERR_IMAGE_PULL = "ErrImagePull"
    CONTAINER_CREATING = "ContainerCreating"
    POD_INITIALIZING = "PodInitializing"

    # Terminated state reasons
    ERROR = "Error"
    COMPLETED = "Completed"
    OOM_KILLED = "OOMKilled"
    CONTAINER_CANNOT_RUN = "ContainerCannotRun"


class LogSource(str, Enum):
    """Source of pod logs - current or previous container."""

    CURRENT = "current"
    PREVIOUS = "previous"


# Error message patterns for fallback detection
# These are substrings that indicate we should try fetching previous logs
FALLBACK_ERROR_PATTERNS = [
    "container is waiting to start",
    "container is in waiting state",
    "container not found",
    "container is terminated",
    "container has been terminated",
    "crashloopbackoff",
    "crash loop back off",
    "waiting to start",
    "pod has been terminated",
    "pod has terminated",
    "previous terminated container",
]

# HTTP status codes for retry logic (already available in http.HTTPStatus, but documenting here)
# RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]  # Handled by HTTPStatus enum


# Diagnostic display constants
class DiagnosticLabel(str, Enum):
    """Labels used in diagnostic output."""

    POD_EVENTS_HEADER = "Recent Pod Events:"
    NO_EVENTS = "No recent pod events found."
    CONTAINER_STATUS_HEADER = "Container '{container}' Status:"
    INIT_CONTAINERS_HEADER = "Init Containers (Failed):"
    STATE_LABEL = "State"
    REASON_LABEL = "Reason"
    MESSAGE_LABEL = "Message"
    EXIT_CODE_LABEL = "Exit Code"
    RESTART_COUNT_LABEL = "Restart Count"
    LAST_TERMINATION_REASON_LABEL = "Last Termination Reason"
    LAST_EXIT_CODE_LABEL = "Last Exit Code"


# Log header templates
LOG_HEADER_CURRENT = "# Showing current logs for container '{container}'"
LOG_HEADER_PREVIOUS = "# Showing previous logs for container '{container}'"
LOG_HEADER_FALLBACK = "# Could not fetch current logs: {reason}"
LOG_HEADER_FALLBACK_SUBTITLE = "# Showing previous logs for container '{container}'"
