import json
import re
from typing import Any, Protocol

import scrubadub

from utils.config import DataSanitizationConfig
from utils.singleton_meta import SingletonMeta

DEFAULT_SENSITIVE_RESOURCES = [
    "Deployment",
    "DeploymentList",
    "Pod",
    "PodList",
    "StatefulSet",
    "StatefulSetList",
    "DaemonSet",
    "DaemonSetList",
    "Job",
    "JobList",
    "CronJob",
    "CronJobList",
]

# List of sensitive environment variable names to remove
DEFAULT_SENSITIVE_ENV_VARS = [
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASS",
    "KEY",
    "AUTH",
    "USERNAME",
    "USER_NAME",
    "CLIENT_ID",
    "CLIENT_SECRET",
]

# Fields that typically contain sensitive data
DEFAULT_SENSITIVE_FIELD_NAMES = [
    "password",
    "secret",
    "token",
    "key",
    "cert",
    "credential",
    "private",
    "auth",
    "username",
    "user_name",
    "firstname",
    "first_name",
    "lastname",
    "last_name",
    "client_id",
    "client_secret",
]

# default fields to exclude from sanitization
DEFAULT_SENSITIVE_FIELD_TO_EXCLUDE = [
    "secretName",
    "authorizers",
]

# default_regex
DEFAULT_REGEX_PATTERNS = [
    r"(?i)(password|passwd|pwd)\s*[=:]\s*[^\s\n]+",  # Passwords
    r"(?i)(api[_-]?key|apikey)\s*[=:]\s*[^\s\n]+",  # API keys
    r"(?i)(secret[_-]?key|secretkey)\s*[=:]\s*[^\s\n]+",  # Secret keys
    r"(?i)(access[_-]?token|accesstoken)\s*[=:]\s*[^\s\n]+",  # Access tokens
    r"\b(Bearer|Token|Key)(?:\s+token)?\s*[:=]?\s*([^\s\n]+)",  # tokens
    r"(?i)(authorization:\s*basic\s+)[a-zA-Z0-9+/=]+",  # Basic auth
    r"(?i)(auth:\s*basic\s+)[a-zA-Z0-9+/=]+",  # Basic auth
    r"(?i)(username|user)\s*[=:]\s*[^\s\n]+",  # Usernames
    r"(?i)(user_name)\s*[=:]\s*[^\s\n]+",  # Usernames
]

REDACTED_VALUE = "[REDACTED]"
SECRET_LIST_KIND_NAME = "SecretList"
SECRET_KIND_NAME = "Secret"


class IDataSanitizer(Protocol):
    """A protocol for a data sanitizer."""

    def sanitize(self, data: str | dict | list[dict]) -> dict | list[dict] | Any:
        """Sanitize the data by removing sensitive information."""
        ...


class DataSanitizer(metaclass=SingletonMeta):
    """Implementation of the data sanitizer that processes input dictionaries."""

    def __init__(self, config: DataSanitizationConfig | None = None):
        self.config = config or DataSanitizationConfig(
            resources_to_sanitize=DEFAULT_SENSITIVE_RESOURCES,
            sensitive_env_vars=DEFAULT_SENSITIVE_ENV_VARS,
            sensitive_field_names=DEFAULT_SENSITIVE_FIELD_NAMES,
            sensitive_field_to_exclude=DEFAULT_SENSITIVE_FIELD_TO_EXCLUDE,
            regex_patterns=DEFAULT_REGEX_PATTERNS,
        )
        self.scrubber = scrubadub.Scrubber()
        self.scrubber.remove_detector(scrubadub.detectors.UrlDetector)

    def sanitize(self, data: str | dict | list[dict]) -> dict | list[dict] | Any:
        """Sanitize the data by removing sensitive information."""
        if isinstance(data, str):
            return self._sanitize_raw_string_data(data)
        elif isinstance(data, list):
            return [
                (
                    self._sanitize_raw_string_data(obj)
                    if isinstance(obj, str)
                    else self._sanitize_object(obj)
                )
                for obj in data
            ]
        elif isinstance(data, dict):
            return self._sanitize_object(data)
        raise ValueError("Data must be a string or list or dictionary.")

    def _sanitize_raw_string_data(
        self, raw_text: str, replacement_text: str = "{{REDACTED}}"
    ) -> str:
        """
        Sanitize raw string data by replacing personal information and credentials.
        """

        # First pass: Use scrubadub for standard PII
        sanitized_text = self.scrubber.clean(raw_text)

        # Second pass: Apply custom credential patterns
        for pattern in self.config.regex_patterns:
            sanitized_text = re.sub(
                pattern, replacement_text, sanitized_text, flags=re.IGNORECASE
            )

        return str(sanitized_text)

    def _sanitize_object(self, obj: dict) -> dict:
        """Sanitize a single object."""
        if not isinstance(obj, dict):
            return obj

        cleaned_obj = self._clean_personal_information(obj)

        # Create a copy to avoid modifying the original
        obj = cleaned_obj.copy()

        # Handle specific Kubernetes resource types
        if "kind" in obj:
            if obj["kind"] == SECRET_KIND_NAME or obj["kind"] == SECRET_LIST_KIND_NAME:
                return self._sanitize_secret(obj)
            elif obj["kind"] in (self.config.resources_to_sanitize or []):
                if "items" in obj:
                    obj["items"] = [
                        self._sanitize_workload(item) for item in obj["items"]
                    ]
                    return obj
                else:
                    return self._sanitize_workload(obj)

        # Recursively sanitize all dictionary fields
        return self._sanitize_dict(obj)

    def _sanitize_secret(self, obj: dict) -> dict:
        """Sanitize a secret object."""
        obj = obj.copy()
        if "items" in obj:  # SecretList
            obj["items"] = [self._sanitize_secret(item) for item in obj["items"]]
        else:  # Secret
            if "data" in obj:
                obj["data"] = {}
            if "stringData" in obj:
                obj["stringData"] = {}
        return obj

    def _sanitize_workload(self, obj: dict) -> dict:
        """Sanitize a workload object (Deployment, Pod, StatefulSet, DaemonSet)."""
        try:
            # First remove last-applied-configuration
            obj = self._remove_last_applied_configuration(obj)
            # Then remove managedFields in metadata if exists
            obj = self._remove_managed_fields_in_metadata(obj)

            # Handle template-based resources (Deployment, StatefulSet, DaemonSet)
            if "spec" in obj and "template" in obj["spec"]:
                containers = obj["spec"]["template"]["spec"]["containers"]
            # Handle Pods
            elif "spec" in obj and "containers" in obj["spec"]:
                containers = obj["spec"]["containers"]
            else:
                return obj

            # Process each container
            for container in containers:
                if "env" in container:
                    container["env"] = self._filter_env_vars(container["env"])

            return obj
        except KeyError:
            return obj

    def _filter_env_vars(self, env_vars: list[dict]) -> list[dict]:
        """Filter out sensitive environment variables."""
        filtered_vars = []
        for env_var in env_vars:
            # Skip if the variable name contains any sensitive keywords
            if any(
                sensitive_key.lower() in env_var.get("name", "").lower()
                for sensitive_key in self.config.sensitive_env_vars
            ):
                # Replace the value with a placeholder
                env_var = env_var.copy()
                if "value" in env_var:
                    env_var["value"] = REDACTED_VALUE

            filtered_vars.append(env_var)
        return filtered_vars

    def _sanitize_dict(self, data: dict) -> dict:
        """Recursively sanitize a dictionary by looking for sensitive data patterns."""
        result = data.copy()

        # First remove last-applied-configuration if exists
        result = self._remove_last_applied_configuration(result)
        # Then remove managedFields in metadata if exists
        result = self._remove_managed_fields_in_metadata(result)

        for key, value in data.items():
            # Check if the key should be excluded from sanitization
            if (
                self.config.sensitive_field_to_exclude
                and key in self.config.sensitive_field_to_exclude
            ):
                result[key] = value
            # Check if the key indicates sensitive data
            elif any(
                sensitive in key.lower()
                for sensitive in self.config.sensitive_field_names
            ):
                result[key] = REDACTED_VALUE
            elif isinstance(value, dict):
                result[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    (self._sanitize_dict(item) if isinstance(item, dict) else item)
                    for item in value
                ]
            else:
                result[key] = value

        return result

    def _clean_personal_information(self, data: dict) -> dict:
        """Cleans personal information from a string."""
        data_str = json.dumps(data)

        sanitized_data_str = self.scrubber.clean(data_str)

        return dict(json.loads(sanitized_data_str))

    @staticmethod
    def _remove_last_applied_configuration(data: dict) -> dict:
        """Remove kubectl.kubernetes.io/last-applied-configuration annotation if it exists."""
        if "metadata" in data and "annotations" in data["metadata"]:
            if (
                "kubectl.kubernetes.io/last-applied-configuration"
                in data["metadata"]["annotations"]
            ):
                del data["metadata"]["annotations"][
                    "kubectl.kubernetes.io/last-applied-configuration"
                ]
            # Remove empty annotations dict if it's the last annotation
            if not data["metadata"]["annotations"]:
                del data["metadata"]["annotations"]
        return data

    @staticmethod
    def _remove_managed_fields_in_metadata(data: dict) -> dict:
        """Remove managedFields in metadata if it exists."""
        if "metadata" in data and "managedFields" in data["metadata"]:
            del data["metadata"]["managedFields"]
        return data
