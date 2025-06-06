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
            "data": {
                "username": "admin",
                "password": "test_password",
                "secret_key": "test_secret_key",
                "secretName": "test_secretName",
            },
        },
    ]

    @pytest.mark.parametrize(
        "custom_config,resource, expected_results",
        [
            (
                DataSanitizationConfig(
                    resources_to_sanitize=["Pod"],
                    sensitive_env_vars=["CUSTOM_SECRET"],
                    sensitive_field_names=["password", "secret_key", "secretName"],
                    sensitive_field_to_exclude=["secretName", "secret_key"],
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
                        "data": {
                            "username": "admin",
                            "password": REDACTED_VALUE,
                            "secret_key": "test_secret_key",  # Not redacted due to exclusion
                            "secretName": "test_secretName",  # Not redacted due to exclusion
                        },
                    },
                ],
            ),
            (
                DataSanitizationConfig(
                    resources_to_sanitize=["Pod"],
                    sensitive_env_vars=["NORMAL_VAR"],
                    sensitive_field_names=["username", "password"],
                    sensitive_field_to_exclude=["username"],
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
                        "data": {
                            "username": "admin",  # Not redacted due to exclusion
                            "password": REDACTED_VALUE,
                            "secret_key": "test_secret_key",
                            "secretName": "test_secretName",
                        },
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
            # job resource with env variables
            (
                {
                    "kind": "Job",
                    "metadata": {"name": "my-job"},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "env": [
                                            {"name": "SECRET_KEY", "value": "secret"}
                                        ],
                                    },
                                ]
                            }
                        }
                    },
                },
                {
                    "kind": "Job",
                    "metadata": {"name": "my-job"},
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
                                            }
                                        ],
                                    }
                                ]
                            }
                        }
                    },
                },
            ),
            # cronjob resource with env variables
            (
                {
                    "kind": "CronJob",
                    "metadata": {"name": "my-cronjob"},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "app",
                                        "env": [
                                            {"name": "SECRET_KEY", "value": "secret"}
                                        ],
                                    }
                                ]
                            },
                        }
                    },
                },
                {
                    "kind": "CronJob",
                    "metadata": {"name": "my-cronjob"},
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
                                            }
                                        ],
                                    }
                                ]
                            },
                        }
                    },
                },
            ),
            # test PV with labels with sensitive data
            (
                {
                    "kind": "PersistentVolume",
                    "metadata": {"name": "my-pv", "labels": {"key": "value"}},
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "capacity": {"storage": "10Gi"},
                        "persistentVolumeReclaimPolicy": "Retain",
                    },
                },
                {
                    "kind": "PersistentVolume",
                    "metadata": {
                        "name": "my-pv",
                        "labels": {"key": REDACTED_VALUE},
                    },
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "capacity": {"storage": "10Gi"},
                        "persistentVolumeReclaimPolicy": "Retain",
                    },
                },
            ),
            # test PVC with labels with sensitive data
            (
                {
                    "kind": "PersistentVolumeClaim",
                    "metadata": {"name": "my-pvc", "labels": {"key": "value"}},
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {"requests": {"storage": "10Gi"}},
                    },
                },
                {
                    "kind": "PersistentVolumeClaim",
                    "metadata": {
                        "name": "my-pvc",
                        "labels": {"key": REDACTED_VALUE},
                    },
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {"requests": {"storage": "10Gi"}},
                    },
                },
            ),
            # test APIRule resources
            (
                {
                    "apiVersion": "gateway.kyma-project.io/v2alpha1",
                    "kind": "APIRule",
                    "metadata": {
                        "name": "my-kyma-resource",
                        "namespace": "kyma-system",
                    },
                    "spec": {
                        "hosts": ["subdomain.domain.com"],
                        "service": {"name": "service", "port": "8080"},
                        "gateway": "kyma-system/kyma-gateway",
                        "rules": [
                            {
                                "jwt": {
                                    "authentications": [
                                        {"issuer": "issuer", "jwksUri": "jwksUri"}
                                    ]
                                },
                                "methods": ["GET"],
                                "path": "/*",
                            }
                        ],
                    },
                },
                {
                    "apiVersion": "gateway.kyma-project.io/v2alpha1",
                    "kind": "APIRule",
                    "metadata": {
                        "name": "my-kyma-resource",
                        "namespace": "kyma-system",
                    },
                    "spec": {
                        "hosts": ["subdomain.domain.com"],
                        "service": {"name": "service", "port": "8080"},
                        "gateway": "kyma-system/kyma-gateway",
                        "rules": [
                            {
                                "jwt": {
                                    "authentications": REDACTED_VALUE,
                                },
                                "methods": ["GET"],
                                "path": "/*",
                            }
                        ],
                    },
                },
            ),
            # test api rule with sensitive data
            (
                {
                    "apiVersion": "gateway.kyma-project.io/v2alpha1",
                    "kind": "APIRule",
                    "metadata": {"name": "test-apirule", "namespace": "test-namespace"},
                    "spec": {
                        "hosts": ["test.domain.com"],
                        "service": {"name": "test-service", "port": "8080"},
                        "gateway": "kyma-gateway/kyma-system",
                        "rules": [
                            {
                                "extAuth": {"authorizers": ["oauth2-proxy"]},
                                "methods": ["GET"],
                                "path": "/*",
                            }
                        ],
                    },
                },
                {
                    "apiVersion": "gateway.kyma-project.io/v2alpha1",
                    "kind": "APIRule",
                    "metadata": {"name": "test-apirule", "namespace": "test-namespace"},
                    "spec": {
                        "hosts": ["test.domain.com"],
                        "service": {"name": "test-service", "port": "8080"},
                        "gateway": "kyma-gateway/kyma-system",
                        "rules": [
                            {
                                "extAuth": REDACTED_VALUE,
                                "methods": ["GET"],
                                "path": "/*",
                            }
                        ],
                    },
                },
            ),
            # test serverless resource
            (
                {
                    "apiVersion": "operator.kyma-project.io/v1alpha1",
                    "kind": "Serverless",
                    "metadata": {
                        "finalizers": [
                            "serverless-operator.kyma-project.io/deletion-hook"
                        ],
                        "name": "default",
                    },
                    "namespace": "kyma-system",
                    "spec": {
                        "dockerRegistry": {
                            "enableInternal": False,
                            "secretName": "my-secret",
                        },
                        "eventing": {
                            "endpoint": "http://eventing-publisher-proxy.kyma-system.svc.cluster.local/publish",
                        },
                        "tracing": {
                            "endpoint": "http://telemetry-otlp-traces.kyma-system.svc.cluster.local:4318/v1/traces",
                        },
                        "secretName": "my-secret",
                    },
                    "eventing": {
                        "endpoint": "http://eventing-publisher-proxy.kyma-system.svc.cluster.local/publish",
                    },
                    "tracing": {
                        "endpoint": "http://telemetry-otlp-traces.kyma-system.svc.cluster.local:4318/v1/traces",
                    },
                    "targetCPUUtilizationPercentage": 50,
                    "functionRequeueDuration": "5m",
                    "functionBuildExecutorArgs": "--insecure,--skip-tls-verify,--skip-unused-stages,--log-format=text,--cache=true,--use-new-run,--compressed-caching=false",
                    "functionBuildMaxSimultaneousJobs": 5,
                    "healthzLivenessTimeout": "10s",
                    "defaultBuildJobPreset": "normal",
                    "defaultRuntimePodPreset": "M",
                },
                {
                    "apiVersion": "operator.kyma-project.io/v1alpha1",
                    "kind": "Serverless",
                    "metadata": {
                        "finalizers": [
                            "serverless-operator.kyma-project.io/deletion-hook"
                        ],
                        "name": "default",
                    },
                    "namespace": "kyma-system",
                    "spec": {
                        "dockerRegistry": {
                            "enableInternal": False,
                            "secretName": "my-secret",
                        },
                        "eventing": {
                            "endpoint": "http://eventing-publisher-proxy.kyma-system.svc.cluster.local/publish",
                        },
                        "tracing": {
                            "endpoint": "http://telemetry-otlp-traces.kyma-system.svc.cluster.local:4318/v1/traces",
                        },
                        "secretName": "my-secret",
                    },
                    "eventing": {
                        "endpoint": "http://eventing-publisher-proxy.kyma-system.svc.cluster.local/publish",
                    },
                    "tracing": {
                        "endpoint": "http://telemetry-otlp-traces.kyma-system.svc.cluster.local:4318/v1/traces",
                    },
                    "targetCPUUtilizationPercentage": 50,
                    "functionRequeueDuration": "5m",
                    "functionBuildExecutorArgs": "--insecure,--skip-tls-verify,--skip-unused-stages,--log-format=text,--cache=true,--use-new-run,--compressed-caching=false",
                    "functionBuildMaxSimultaneousJobs": 5,
                    "healthzLivenessTimeout": "10s",
                    "defaultBuildJobPreset": "normal",
                    "defaultRuntimePodPreset": "M",
                },
            ),
            # delete "kubectl.kubernetes.io/last-applied-configuration" field completely
            (
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {
                        "annotations": {
                            "deployment.kubernetes.io/revision": "1",
                            "kubectl.kubernetes.io/last-applied-configuration": '{"apiVersion":"apps/v1","kind":"Deployment","metadata":{"annotations":{},"labels":{"app":"nginx"},"name":"nginx","namespace":"test-sanit"},"spec":{"replicas":3,"selector":{"matchLabels":{"app":"nginx"}},"template":{"metadata":{"labels":{"app":"nginx"}},"spec":{"containers":[{"env":[{"name":"TOKEN","value":"test token"},{"name":"PASSWORD","value":"test password"},{"name":"CLIENT_ID","value":"test client ID"},{"name":"USER_NAME","value":"test user name"}],"image":"nginx:1.14.2","name":"nginx","ports":[{"containerPort":80}]}]}}}}\n',
                        },
                    },
                    "name": "nginx",
                    "namespace": "test-sanit",
                    "spec": {
                        "progressDeadlineSeconds": 600,
                        "replicas": 3,
                        "revisionHistoryLimit": 10,
                        "selector": {"matchLabels": {"app": "nginx"}},
                        "strategy": {
                            "rollingUpdate": {
                                "maxSurge": "25%",
                                "maxUnavailable": "25%",
                            },
                            "type": "RollingUpdate",
                        },
                        "template": {
                            "metadata": {
                                "labels": {"app": "nginx"},
                            },
                            "spec": {
                                "containers": [
                                    {
                                        "env": [
                                            {"name": "TOKEN", "value": "test token"},
                                            {
                                                "name": "PASSWORD",
                                                "value": "test password",
                                            },
                                            {
                                                "name": "CLIENT_ID",
                                                "value": "test client ID",
                                            },
                                            {
                                                "name": "USER_NAME",
                                                "value": "test user name",
                                            },
                                        ],
                                        "image": "nginx:1.14.2",
                                        "name": "nginx",
                                        "ports": [{"containerPort": 80}],
                                    }
                                ],
                            },
                        },
                    },
                },
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {
                        "annotations": {
                            "deployment.kubernetes.io/revision": "1",
                        }
                    },
                    "name": "nginx",
                    "namespace": "test-sanit",
                    "spec": {
                        "progressDeadlineSeconds": 600,
                        "replicas": 3,
                        "revisionHistoryLimit": 10,
                        "selector": {"matchLabels": {"app": "nginx"}},
                        "strategy": {
                            "rollingUpdate": {
                                "maxSurge": "25%",
                                "maxUnavailable": "25%",
                            },
                            "type": "RollingUpdate",
                        },
                        "template": {
                            "metadata": {
                                "labels": {"app": "nginx"},
                            },
                            "spec": {
                                "containers": [
                                    {
                                        "env": [
                                            {"name": "TOKEN", "value": REDACTED_VALUE},
                                            {
                                                "name": "PASSWORD",
                                                "value": REDACTED_VALUE,
                                            },
                                            {
                                                "name": "CLIENT_ID",
                                                "value": REDACTED_VALUE,
                                            },
                                            {
                                                "name": "USER_NAME",
                                                "value": REDACTED_VALUE,
                                            },
                                        ],
                                        "image": "nginx:1.14.2",
                                        "name": "nginx",
                                        "ports": [{"containerPort": 80}],
                                    }
                                ],
                            },
                        },
                    },
                },
            ),
        ],
    )
    def test_kubernetes_resources(self, test_data, expected_results):
        """Test sanitization of various Kubernetes resource types and edge cases."""
        sanitized = self.data_sanitizer.sanitize(test_data)
        assert sanitized == expected_results
