import pytest

from services.data_sanitizer import REDACTED_VALUE, DataSanitizer
from utils.config import DataSanitizationConfig


class TestDataSanitizer:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset the DataSanitizer singleton between tests."""
        DataSanitizer._instances = {}
        self.data_sanitizer = DataSanitizer()
        yield

    test_data = [
        {
            "kind": "Pod",
            "metadata": {
                "name": "my-pod",
                "customer_id": "123",
            },
            "spec": {
                "containers": [
                    {
                        "name": "app",
                        "env": [
                            {"name": "CUSTOM_SECRET", "value": "custom_secret"},
                            {"name": "NORMAL_VAR", "value": "normal_val"},
                            {"name": "SECRET_VAR", "value": "secret_val"},
                        ],
                    }
                ]
            },
        },
        {
            "kind": "ConfigMap",
            "metadata": {"name": "my-configmap"},
            "data": {"username": "admin", "password": "secret"},
        },
    ]

    @pytest.mark.parametrize(
        "custom_config,resource, expected_results",
        [
            (
                DataSanitizationConfig(
                    resources_to_sanitize=["Pod"],
                    sensitive_env_vars=["CUSTOM_SECRET"],
                    sensitive_field_names=["password"],
                ),
                test_data,
                [
                    {
                        "kind": "Pod",
                        "metadata": {
                            "name": "my-pod",
                            "customer_id": "123",
                        },
                        "spec": {
                            "containers": [
                                {
                                    "name": "app",
                                    "env": [
                                        {
                                            "name": "CUSTOM_SECRET",
                                            "value": REDACTED_VALUE,
                                        },
                                        {"name": "NORMAL_VAR", "value": "normal_val"},
                                        {"name": "SECRET_VAR", "value": "secret_val"},
                                    ],
                                }
                            ]
                        },
                    },
                    {
                        "kind": "ConfigMap",
                        "metadata": {"name": "my-configmap"},
                        "data": {"username": "admin", "password": REDACTED_VALUE},
                    },
                ],
            ),
            (
                DataSanitizationConfig(
                    resources_to_sanitize=["Pod"],
                    sensitive_env_vars=["NORMAL_VAR"],
                    sensitive_field_names=["username"],
                ),
                test_data,
                [
                    {
                        "kind": "Pod",
                        "metadata": {
                            "name": "my-pod",
                            "customer_id": "123",
                        },
                        "spec": {
                            "containers": [
                                {
                                    "name": "app",
                                    "env": [
                                        {
                                            "name": "CUSTOM_SECRET",
                                            "value": "custom_secret",
                                        },
                                        {"name": "NORMAL_VAR", "value": REDACTED_VALUE},
                                        {"name": "SECRET_VAR", "value": "secret_val"},
                                    ],
                                }
                            ]
                        },
                    },
                    {
                        "kind": "ConfigMap",
                        "metadata": {"name": "my-configmap"},
                        "data": {"username": REDACTED_VALUE, "password": "secret"},
                    },
                ],
            ),
        ],
    )
    def test_custom_config(self, custom_config, resource, expected_results):
        """Test DataSanitizer with custom configuration."""
        DataSanitizer._instances = {}  # reset singleton instance
        sanitizer = DataSanitizer(config=custom_config)
        sanitized = sanitizer.sanitize(resource)
        assert sanitized == expected_results

    @pytest.mark.parametrize(
        "k8s_resource,expected_results",
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
                    "stringData": {
                        "username": "admin",
                        "password": "super-secret",
                    },
                },
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "metadata": {"name": "my-secret"},
                    "data": {},
                    "stringData": {},
                },
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
                {
                    "apiVersion": "v1",
                    "kind": "SecretList",
                    "items": [
                        {
                            "apiVersion": "v1",
                            "kind": "Secret",
                            "metadata": {"name": "secret1"},
                            "data": {},
                        },
                        {
                            "apiVersion": "v1",
                            "kind": "Secret",
                            "metadata": {"name": "secret2"},
                            "data": {},
                        },
                    ],
                },
            ),
        ],
    )
    def test_sanitize_k8s_secrets(self, k8s_resource, expected_results):
        """Test sanitization of Kubernetes Secret resources."""
        sanitized = self.data_sanitizer.sanitize(k8s_resource)
        assert sanitized == expected_results

    @pytest.mark.parametrize(
        "test_data,expected_results, error",
        [
            # Basic data structure test
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
                    "username": REDACTED_VALUE,
                    "password": REDACTED_VALUE,
                    "email": "{{EMAIL}}",
                    "first_name": REDACTED_VALUE,
                    "last_name": REDACTED_VALUE,
                    "settings": {
                        "debug": True,
                        "secret_key": REDACTED_VALUE,
                        "database": {
                            "host": "localhost",
                            "password": REDACTED_VALUE,
                        },
                    },
                },
                None,
            ),
            # List of dictionaries test
            (
                [
                    {"name": "app1", "api_key": "key1"},
                    {"name": "app2", "api_key": "key2"},
                ],
                [
                    {"name": "app1", "api_key": REDACTED_VALUE},
                    {"name": "app2", "api_key": REDACTED_VALUE},
                ],
                None,
            ),
            # Nested PII test
            (
                {
                    "kind": "ConfigMap",
                    "metadata": {
                        "name": "app-config",
                        "annotations": {
                            "description": "Contact email: john.doe@example.com",
                            "nested": {
                                "contact": "phone: 1800 555-5555",
                                "details": {
                                    "address": "123 Main St, NY",
                                    "ssn": "123-45-6789",
                                },
                            },
                        },
                    },
                    "data": {
                        "config.json": '{"admin_email": "admin@example.com"}',
                    },
                },
                {
                    "kind": "ConfigMap",
                    "metadata": {
                        "name": "app-config",
                        "annotations": {
                            "description": "Contact email: {{EMAIL}}",
                            "nested": {
                                "contact": "phone: {{PHONE}}",
                                "details": {
                                    "address": "123 Main St, NY",
                                    "ssn": "{{SOCIAL_SECURITY_NUMBER}}",
                                },
                            },
                        },
                    },
                    "data": {
                        "config.json": '{"admin_email": "{{EMAIL}}"}',
                    },
                },
                None,
            ),
            # Mixed list with PII
            (
                {
                    "users": [
                        {"name": "John Doe", "email": "john@example.com"},
                        {"name": "Jane Smith", "phone": "1800 555-5555"},
                        {"name": "Bob Wilson", "normal_field": "value"},
                    ]
                },
                {
                    "users": [
                        {"name": "John Doe", "email": "{{EMAIL}}"},
                        {"name": "Jane Smith", "phone": "{{PHONE}}"},
                        {"name": "Bob Wilson", "normal_field": "value"},
                    ]
                },
                None,
            ),
            (
                {
                    "email": "john.doe@example.com",
                    "phone": "+49 555 1234567",
                    "description": "any test information",
                },
                {
                    "email": "{{EMAIL}}",
                    "phone": "{{PHONE}}",
                    "description": "any test information",
                },
                None,
            ),
            # personal information in yaml file
            (
                {
                    "kind": "ConfigMap",
                    "metadata": {"name": "my-configmap"},
                    "data": {
                        "email": "john.doe@example.com",
                        "phone": "+49 555 1234567",
                        "description": "any test information",
                    },
                },
                {
                    "kind": "ConfigMap",
                    "metadata": {"name": "my-configmap"},
                    "data": {
                        "email": "{{EMAIL}}",
                        "phone": "{{PHONE}}",
                        "description": "any test information",
                    },
                },
                None,
            ),
            # invalid input
            (
                "invalid input",
                None,
                ValueError,
            ),
        ],
    )
    def test_data_structures_and_pii(self, test_data, expected_results, error):
        """Test sanitization of various data structures and PII data."""
        if error:
            with pytest.raises(error, match="Data must be a list or a dictionary."):
                self.data_sanitizer.sanitize(test_data)
        else:
            sanitized = self.data_sanitizer.sanitize(test_data)
            assert sanitized == expected_results

    @pytest.mark.parametrize(
        "test_data,expected_results",
        [
            # StatefulSet test
            (
                {
                    "kind": "StatefulSet",
                    "metadata": {"name": "stateful-app"},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "env": [
                                            {
                                                "name": "SECRET_KEY",
                                                "value": "secret",
                                            },
                                            {
                                                "name": "NORMAL_KEY",
                                                "value": "normal",
                                            },
                                        ],
                                    }
                                ]
                            }
                        }
                    },
                },
                {
                    "kind": "StatefulSet",
                    "metadata": {"name": "stateful-app"},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "env": [
                                            {
                                                "name": "SECRET_KEY",
                                                "value": REDACTED_VALUE,
                                            },
                                            {
                                                "name": "NORMAL_KEY",
                                                "value": REDACTED_VALUE,
                                            },
                                        ],
                                    }
                                ]
                            }
                        }
                    },
                },
            ),
            # DaemonSet test
            (
                {
                    "kind": "DaemonSet",
                    "metadata": {"name": "daemon-app"},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "env": [
                                            {"name": "API_TOKEN", "value": "token123"},
                                            {"name": "LOG_LEVEL", "value": "debug"},
                                        ],
                                    }
                                ]
                            }
                        }
                    },
                },
                {
                    "kind": "DaemonSet",
                    "metadata": {"name": "daemon-app"},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "env": [
                                            {
                                                "name": "API_TOKEN",
                                                "value": REDACTED_VALUE,
                                            },
                                            {"name": "LOG_LEVEL", "value": "debug"},
                                        ],
                                    }
                                ]
                            }
                        }
                    },
                },
            ),
            # Empty containers test
            (
                {
                    "kind": "Pod",
                    "metadata": {"name": "empty-pod"},
                    "spec": {"containers": []},
                },
                {
                    "kind": "Pod",
                    "metadata": {"name": "empty-pod"},
                    "spec": {"containers": []},
                },
            ),
            # Null/empty value tests
            (
                {
                    "kind": "Pod",
                    "metadata": {"name": "null-pod"},
                    "spec": {
                        "containers": [
                            {
                                "name": "app",
                                "env": [
                                    {"name": "SECRET_KEY", "value": None},
                                    {"name": "EMPTY_SECRET", "value": ""},
                                ],
                            }
                        ]
                    },
                },
                {
                    "kind": "Pod",
                    "metadata": {"name": "null-pod"},
                    "spec": {
                        "containers": [
                            {
                                "name": "app",
                                "env": [
                                    {"name": "SECRET_KEY", "value": REDACTED_VALUE},
                                    {"name": "EMPTY_SECRET", "value": REDACTED_VALUE},
                                ],
                            }
                        ]
                    },
                },
            ),
            # valueFrom only test
            (
                {
                    "kind": "Pod",
                    "metadata": {"name": "value-from-pod"},
                    "spec": {
                        "containers": [
                            {
                                "name": "app",
                                "env": [
                                    {
                                        "name": "SECRET_KEY",
                                        "valueFrom": {
                                            "secretKeyRef": {
                                                "name": "secret",
                                                "key": "key",
                                            }
                                        },
                                    }
                                ],
                            }
                        ]
                    },
                },
                {
                    "kind": "Pod",
                    "metadata": {"name": "value-from-pod"},
                    "spec": {
                        "containers": [
                            {
                                "name": "app",
                                "env": [
                                    {
                                        "name": "SECRET_KEY",
                                        "valueFrom": {
                                            "secretKeyRef": {
                                                "name": "secret",
                                                "key": "key",
                                            }
                                        },
                                    }
                                ],
                            }
                        ]
                    },
                },
            ),
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
                                            {
                                                "name": "EMAIL",
                                                "value": "admin@example.com",
                                            },
                                            {"name": "NAME", "value": "John Doe"},
                                            {
                                                "name": "API_TOKEN",
                                                "value": "secret-token",
                                            },
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
                                            {
                                                "name": "EMAIL",
                                                "value": "{{EMAIL}}",
                                            },
                                            {"name": "NAME", "value": "John Doe"},
                                            {
                                                "name": "API_TOKEN",
                                                "value": REDACTED_VALUE,
                                            },
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
                                    {"name": "SECRET_KEY", "value": REDACTED_VALUE},
                                    {"name": "NAME", "value": "John Doe"},
                                    {"name": "EMAIL", "value": "{{EMAIL}}"},
                                ],
                            }
                        ]
                    },
                },
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
                                    {"name": "NAME", "value": "John Doe"},
                                    {"name": "TEST1", "value": "test1"},
                                    {"name": "TEST2", "value": "test2"},
                                ],
                            }
                        ]
                    },
                },
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
                                    {"name": "NAME", "value": "John Doe"},
                                    {"name": "TEST1", "value": "test1"},
                                    {"name": "TEST2", "value": "test2"},
                                ],
                            }
                        ]
                    },
                },
            ),
        ],
    )
    def test_kubernetes_resources(self, test_data, expected_results):
        """Test sanitization of various Kubernetes resource types and edge cases."""
        sanitized = self.data_sanitizer.sanitize(test_data)
        assert sanitized == expected_results
