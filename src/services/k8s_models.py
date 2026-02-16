"""Pydantic models for Kubernetes service responses."""

from pydantic import BaseModel, Field


class ContainerStatus(BaseModel):
    """Container status information."""

    state: str = Field(..., description="Container state: Running, Waiting, or Terminated")
    reason: str | None = Field(default=None, description="Reason for the current state")
    message: str | None = Field(default=None, description="Detailed message about the state")
    exit_code: int | None = Field(default=None, description="Exit code if terminated", serialization_alias="exitCode")
    restart_count: int = Field(
        default=0, description="Number of times container has been restarted", serialization_alias="restartCount"
    )
    last_termination_reason: str | None = Field(
        default=None, description="Reason for last termination", serialization_alias="lastTerminationReason"
    )
    last_exit_code: int | None = Field(
        default=None, description="Exit code from last termination", serialization_alias="lastExitCode"
    )


class InitContainerStatus(BaseModel):
    """Init container status information."""

    ready: bool = Field(..., description="Whether the init container completed successfully")
    state: str = Field(..., description="Init container state: Running, Waiting, or Terminated")
    reason: str | None = Field(default=None, description="Reason for the current state")
    message: str | None = Field(default=None, description="Detailed message about the state")
    exit_code: int | None = Field(default=None, description="Exit code if terminated", serialization_alias="exitCode")
    restart_count: int = Field(
        default=0, description="Number of times init container has been restarted", serialization_alias="restartCount"
    )


class PodLogsDiagnosticContext(BaseModel):
    """Diagnostic context when container logs are unavailable."""

    events: str = Field(..., description="Formatted text of recent pod events")
    container_statuses: dict[str, ContainerStatus] | None = Field(
        default=None,
        description="Structured status information for each container",
    )
    init_container_statuses: dict[str, InitContainerStatus] | None = Field(
        default=None,
        description="Structured status information for each init container",
    )


class PodLogs(BaseModel):
    """Container log contents."""

    current_container: str = Field(..., description="Current container logs as string with newlines")
    previously_terminated_container: str = Field(
        ..., description="Previously terminated container logs as string with newlines or unavailability message"
    )


class PodLogsResult(BaseModel):
    """Complete container logs result with optional diagnostic context."""

    logs: PodLogs = Field(..., description="Container logs for current and previously terminated container instances")
    diagnostic_context: PodLogsDiagnosticContext | None = Field(
        default=None,
        description="Optional diagnostic information when current container logs are unavailable",
    )
