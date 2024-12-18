class DataSanitizer:
    """Implementation of the data sanitizer that processes input dictionaries."""

    # List of sensitive environment variable names to remove
    SENSITIVE_ENV_VARS = {
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "PASS",
        "KEY",
        "CERT",
        "PRIVATE",
        "CREDENTIAL",
        "AUTH",
    }

    # Fields that typically contain sensitive data
    SENSITIVE_FIELD_NAMES = {
        "password",
        "secret",
        "token",
        "key",
        "cert",
        "credential",
        "private",
        "auth",
    }

    @staticmethod
    def sanitize(data: dict | list[dict]) -> dict | list[dict]:
        """Sanitize the data by removing sensitive information."""
        if isinstance(data, list):
            return [DataSanitizer._sanitize_object(obj) for obj in data]
        elif isinstance(data, dict):
            return DataSanitizer._sanitize_object(data)
        raise ValueError("Data must be a list or a dictionary.")

    @staticmethod
    def _sanitize_object(obj: dict) -> dict:
        """Sanitize a single object."""
        if not isinstance(obj, dict):
            return obj

        # Create a copy to avoid modifying the original
        obj = obj.copy()

        # Handle specific Kubernetes resource types
        if "kind" in obj:
            if obj["kind"] == "Secret" or obj["kind"] == "SecretList":
                if "items" in obj:
                    return [
                        DataSanitizer._sanitize_secret(item) for item in obj["items"]
                    ]  # type: ignore
                else:
                    return DataSanitizer._sanitize_secret(obj)
            elif obj["kind"] in [
                "Deployment",
                "DeploymentList",
                "Pod",
                "PodList",
                "StatefulSet",
                "StatefulSetList",
                "DaemonSet",
                "DaemonSetList",
            ]:
                if "items" in obj:
                    return [
                        DataSanitizer._sanitize_workload(item) for item in obj["items"]
                    ]  # type: ignore
                else:
                    return DataSanitizer._sanitize_workload(obj)

        # Recursively sanitize all dictionary fields
        return DataSanitizer._sanitize_dict(obj)

    @staticmethod
    def _sanitize_secret(obj: dict) -> dict:
        """Sanitize a secret object."""
        obj["data"] = {}
        return obj

    @staticmethod
    def _sanitize_workload(obj: dict) -> dict:
        """Sanitize a workload object (Deployment, Pod, StatefulSet, DaemonSet)."""
        try:
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
                    container["env"] = DataSanitizer._filter_env_vars(container["env"])
                if "envFrom" in container:
                    # Remove all envFrom references as they might contain sensitive data
                    container["envFrom"] = []

            return obj
        except KeyError:
            # If the structure is not as expected, return the original object
            return obj

    @staticmethod
    def _filter_env_vars(env_vars: list) -> list:
        """Filter out sensitive environment variables."""
        filtered_vars = []
        for env_var in env_vars:
            # Skip if the variable name contains any sensitive keywords
            if any(
                sensitive_key.lower() in env_var.get("name", "").lower()
                for sensitive_key in DataSanitizer.SENSITIVE_ENV_VARS
            ):
                # Replace the value with a placeholder
                env_var = env_var.copy()
                if "value" in env_var:
                    env_var["value"] = "[REDACTED]"
                if "valueFrom" in env_var:
                    env_var["valueFrom"] = {"description": "[REDACTED]"}
            filtered_vars.append(env_var)
        return filtered_vars

    @staticmethod
    def _sanitize_dict(data: dict) -> dict:
        """Recursively sanitize a dictionary by looking for sensitive data patterns."""
        result = data.copy()

        for key, value in data.items():
            # Check if the key indicates sensitive data
            key_lower = key.lower()
            if any(
                sensitive in key_lower
                for sensitive in DataSanitizer.SENSITIVE_FIELD_NAMES
            ):
                result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = DataSanitizer._sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    (
                        DataSanitizer._sanitize_dict(item)
                        if isinstance(item, dict)
                        else item
                    )
                    for item in value
                ]
            else:
                result[key] = value

        return result
