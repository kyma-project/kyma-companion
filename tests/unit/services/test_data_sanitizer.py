import pytest

from services.data_sanitizer import DataSanitizer


def test_sanitize_invalid_input():
    """Test that sanitize raises ValueError for invalid input types."""
    with pytest.raises(ValueError, match="Data must be a list or a dictionary."):
        DataSanitizer.sanitize("invalid input")


@pytest.mark.parametrize(
    "k8s_resource,resource_type",
    [
        (
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "my-secret"},
                "data": {
                    "username": "admin",
                    "password": "super-secret",
                },
            },
            "Secret",
        ),
        (
            {
                "apiVersion": "v1",
                "kind": "SecretList",
                "items": [
                    {
                        "apiVersion": "v1",
                        "kind": "Secret",
                        "metadata": {"name": "secret1"},
                        "data": {"key1": "value1"},
                    },
                    {
                        "apiVersion": "v1",
                        "kind": "Secret",
                        "metadata": {"name": "secret2"},
                        "data": {"key2": "value2"},
                    },
                ],
            },
            "SecretList",
        ),
    ],
)
def test_sanitize_k8s_secrets(k8s_resource, resource_type):
    """Test sanitization of Kubernetes Secret resources."""
    sanitized = DataSanitizer.sanitize(k8s_resource)

    if resource_type == "Secret":
        assert sanitized["kind"] == "Secret"
        assert sanitized["metadata"]["name"] == "my-secret"
        assert sanitized["data"] == {}
    else:  # SecretList
        assert isinstance(sanitized, list)
        assert len(sanitized) == 2
        assert all(item["data"] == {} for item in sanitized)


@pytest.mark.parametrize(
    "k8s_resource,resource_type",
    [
        (
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "my-app"},
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "app",
                                    "env": [
                                        {"name": "DEBUG", "value": "true"},
                                        {"name": "EMAIL", "value": "admin@example.com"},
                                        {"name": "NAME", "value": "John Doe"},
                                        {"name": "API_TOKEN", "value": "secret-token"},
                                        {
                                            "name": "DB_PASSWORD",
                                            "valueFrom": {
                                                "secretKeyRef": {
                                                    "name": "db-secret",
                                                    "key": "password",
                                                }
                                            },
                                        },
                                    ],
                                    "envFrom": [
                                        {"secretRef": {"name": "app-secrets"}},
                                        {"configMapRef": {"name": "app-config"}},
                                    ],
                                }
                            ]
                        }
                    }
                },
            },
            "Deployment",
        ),
        (
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "my-pod"},
                "spec": {
                    "containers": [
                        {
                            "name": "app",
                            "env": [
                                {"name": "APP_NAME", "value": "my-app"},
                                {"name": "SECRET_KEY", "value": "very-secret"},
                                {"name": "NAME", "value": "John Doe"},
                                {"name": "EMAIL", "value": "admin@example.com"},
                            ],
                        }
                    ]
                },
            },
            "Pod",
        ),
    ],
)
def test_sanitize_k8s_workloads(k8s_resource, resource_type):
    """Test sanitization of Kubernetes workload resources."""
    sanitized = DataSanitizer.sanitize(k8s_resource)

    if resource_type == "Deployment":
        containers = sanitized["spec"]["template"]["spec"]["containers"]
        env_vars = containers[0]["env"]

        assert any(
            var["name"] == "DEBUG" and var["value"] == "true" for var in env_vars
        )
        assert any(
            var["name"] == "API_TOKEN" and var["value"] == "[REDACTED]"
            for var in env_vars
        )
        assert any(
            var["name"] == "DB_PASSWORD"
            and var["valueFrom"] == {"description": "[REDACTED]"}
            for var in env_vars
        )
        assert any(
            var["name"] == "EMAIL" and var["value"] == "{{EMAIL}}" for var in env_vars
        )
        assert containers[0]["envFrom"] == []

    else:  # Pod
        env_vars = sanitized["spec"]["containers"][0]["env"]
        assert any(
            var["name"] == "APP_NAME" and var["value"] == "my-app" for var in env_vars
        )
        assert any(
            var["name"] == "SECRET_KEY" and var["value"] == "[REDACTED]"
            for var in env_vars
        )
        assert any(
            var["name"] == "EMAIL" and var["value"] == "{{EMAIL}}" for var in env_vars
        )


@pytest.mark.parametrize(
    "test_data,expected_results",
    [
        (
            {
                "username": "admin",
                "password": "secret123",
                "email": "admin@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "settings": {
                    "debug": True,
                    "secret_key": "abc123",
                    "database": {
                        "host": "localhost",
                        "password": "db-password",
                    },
                },
            },
            {
                "username_preserved": ("username", "admin"),
                "password_redacted": ("password", "[REDACTED]"),
                "email_hidden": ("email", "{{EMAIL}}"),
                "first_name_hidden": ("first_name", "{{FIRST_NAME}}"),
                "last_name_hidden": ("last_name", "{{LAST_NAME}}"),
                "nested_preserved": ("debug", True),
                "nested_redacted": ("secret_key", "[REDACTED]"),
                "deeply_nested_preserved": ("host", "localhost"),
                "deeply_nested_redacted": ("password", "[REDACTED]"),
            },
        ),
        (
            [
                {"name": "app1", "api_key": "key1"},
                {"name": "app2", "api_key": "key2"},
            ],
            {
                "length": 2,
                "names_preserved": True,
                "sensitive_redacted": True,
            },
        ),
    ],
)
def test_sanitize_data_structures(test_data, expected_results):
    """Test sanitization of various data structures."""
    sanitized = DataSanitizer.sanitize(test_data)

    if isinstance(test_data, dict):
        assert (
            sanitized[expected_results["username_preserved"][0]]
            == expected_results["username_preserved"][1]
        )
        assert (
            sanitized[expected_results["password_redacted"][0]]
            == expected_results["password_redacted"][1]
        )
        assert (
            sanitized[expected_results["email_hidden"][0]]
            == expected_results["email_hidden"][1]
        )
        assert (
            sanitized["settings"][expected_results["nested_preserved"][0]]
            == expected_results["nested_preserved"][1]
        )
        assert (
            sanitized["settings"][expected_results["nested_redacted"][0]]
            == expected_results["nested_redacted"][1]
        )
        assert (
            sanitized["settings"]["database"][
                expected_results["deeply_nested_preserved"][0]
            ]
            == expected_results["deeply_nested_preserved"][1]
        )
        assert (
            sanitized["settings"]["database"][
                expected_results["deeply_nested_redacted"][0]
            ]
            == expected_results["deeply_nested_redacted"][1]
        )
    else:  # list
        assert len(sanitized) == expected_results["length"]
        assert all(item["name"].startswith("app") for item in sanitized)
        assert all(item["api_key"] == "[REDACTED]" for item in sanitized)
