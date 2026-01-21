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
                ("invalid input", "invalid input"),
                None,
                ValueError,
            ),
        ],
    )
    def test_data_structures_and_pii(self, test_data, expected_results, error):
        """Test sanitization of various data structures and PII data."""
        if error:
            with pytest.raises(error, match="Data must be a string or list or dictionary."):
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
                                        "env": [{"name": "SECRET_KEY", "value": "secret"}],
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
                                        "env": [{"name": "SECRET_KEY", "value": "secret"}],
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
                                "jwt": {"authentications": [{"issuer": "issuer", "jwksUri": "jwksUri"}]},
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
                        "finalizers": ["serverless-operator.kyma-project.io/deletion-hook"],
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
                        "finalizers": ["serverless-operator.kyma-project.io/deletion-hook"],
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
            # delete managedFields in metadata
            (
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {
                        "name": "my-app",
                        "managedFields": [{"name": "my-app"}],
                    },
                    "spec": {
                        "replicas": 3,
                        "selector": {"matchLabels": {"app": "my-app"}},
                        "template": {"metadata": {"labels": {"app": "my-app"}}},
                    },
                },
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": "my-app"},
                    "spec": {
                        "replicas": 3,
                        "selector": {"matchLabels": {"app": "my-app"}},
                        "template": {"metadata": {"labels": {"app": "my-app"}}},
                    },
                },
            ),
        ],
    )
    def test_kubernetes_resources(self, test_data, expected_results):
        """Test sanitization of various Kubernetes resource types and edge cases."""
        sanitized = self.data_sanitizer.sanitize(test_data)
        assert sanitized == expected_results

    @pytest.mark.parametrize(
        "input_text,expected_contains,test_description",
        [
            # Password patterns
            ("password=secret123", "{{REDACTED}}", "password with equals"),
            ("Password: mypassword", "{{REDACTED}}", "password with colon uppercase"),
            ("passwd=admin123", "{{REDACTED}}", "passwd abbreviation"),
            ("pwd: letmein", "{{REDACTED}}", "pwd abbreviation"),
            ("PASSWORD = strongpass", "{{REDACTED}}", "password with spaces"),
            # API Key patterns
            ("api_key=sk-1234567890abcdef", "{{REDACTED}}", "api_key with underscore"),
            ("api-key: xyz789", "{{REDACTED}}", "api-key with hyphen"),
            ("apikey=abcd1234", "{{REDACTED}}", "apikey no separator"),
            ("API_KEY: test123", "{{REDACTED}}", "API_KEY uppercase"),
            # Secret key patterns
            ("secret_key=mysecret", "{{REDACTED}}", "secret_key with underscore"),
            ("secret-key: topsecret", "{{REDACTED}}", "secret-key with hyphen"),
            ("secretkey=hidden", "{{REDACTED}}", "secretkey no separator"),
            ("SECRET_KEY: classified", "{{REDACTED}}", "SECRET_KEY uppercase"),
            # Access token patterns
            ("access_token=bearer123", "{{REDACTED}}", "access_token with underscore"),
            ("access-token: token456", "{{REDACTED}}", "access-token with hyphen"),
            ("accesstoken=mytoken", "{{REDACTED}}", "accesstoken no separator"),
            ("ACCESS_TOKEN: xyz", "{{REDACTED}}", "ACCESS_TOKEN uppercase"),
            # Bearer token patterns
            (
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                "{{REDACTED}}",
                "bearer token JWT-like",
            ),
            ("bearer abc123def456", "{{REDACTED}}", "bearer token simple"),
            (
                "BEARER token_with_special-chars.+/=",
                "{{REDACTED}}",
                "bearer uppercase with special chars",
            ),
            # Basic auth patterns
            (
                "Authorization: Basic dXNlcjpwYXNz",
                "{{REDACTED}}",
                "authorization basic",
            ),
            (
                "authorization: basic YWRtaW46YWRtaW4=",
                "{{REDACTED}}",
                "authorization basic lowercase",
            ),
            (
                "Auth: Basic bXl1c2VyOnNlY3JldA==",
                "{{REDACTED}}",
                "auth basic short form",
            ),
            ("auth: basic dGVzdDp0ZXN0", "{{REDACTED}}", "auth basic lowercase"),
            # Long alphanumeric strings (32+ chars)
            (
                "This is a token: 1234567890abcdef1234567890abcdef",
                "This is a {{REDACTED}}",
                "32 char hash token",
            ),
            (
                "This is a hash: 1234567890abcdef1234567890abcdef",
                "This is a hash: 1234567890abcdef1234567890abcdef",
                "just a hash with a prefix of key or token should not redacted",
            ),
            (
                "Token: abcdef1234567890abcdef1234567890abcdef",
                "{{REDACTED}}",
                "40 char token",
            ),
            (
                "Key: 123456789012345678901234567890123456789012345678901234567890abcd",
                "{{REDACTED}}",
                "64 char key",
            ),
            # Username patterns
            ("username=johndoe", "{{REDACTED}}", "username with equals"),
            ("user: admin", "{{REDACTED}}", "user with colon"),
            ("USERNAME = testuser", "{{REDACTED}}", "USERNAME uppercase with spaces"),
            ("User: service_account", "{{REDACTED}}", "User capitalized"),
            # Multiple patterns in one string
            (
                "username=admin password=secret api_key=sk-123456",
                "{{REDACTED}} {{REDACTED}} {{REDACTED}}",
                "multiple credentials",
            ),
            # Edge cases - should NOT be redacted
            (
                "This is a short string",
                "This is a short string",
                "normal text unchanged",
            ),
            ("password", "password", "keyword alone without assignment"),
            ("api_key", "api_key", "api_key without value"),
            ("Short123", "Short123", "short alphanumeric string"),
            ("email@example.com", "{{EMAIL}}", "email format"),
            # Case sensitivity tests
            ("PASSWORD=TEST123", "{{REDACTED}}", "all caps password"),
            ("Api_Key=test", "{{REDACTED}}", "mixed case api key"),
            # Different separators and spacing
            (
                "api_key:   token_with_leading_spaces",
                "{{REDACTED}}",
                "api_key with leading spaces after colon",
            ),
            # Complex real-world examples , not redacting url as this can be used by llm to identify problems
            (
                "curl -H 'Authorization: Bearer abc123def456' https://api.example.com",
                "curl -H 'Authorization: {{REDACTED}} https://api.example.com",
                "curl command with bearer",
            ),
            # Multiline scenarios
            (
                "line1\npassword=secret\nline3",
                "line1\n{{REDACTED}}\nline3",
                "multiline with password",
            ),
            # Special characters in credentials
            ("password=p@ssw0rd!", "{{REDACTED}}", "password with special chars"),
            (
                "api_key=sk-proj-1234567890abcdef",
                "{{REDACTED}}",
                "api key with project prefix",
            ),
            # Mixed sensitive data in single log line
            (
                "User john@example.com logged with user=admin password=admin123",
                "User {{EMAIL}} logged with {{REDACTED}} {{REDACTED}}",
                "Mixed sensitive data in single log line",
            ),
        ],
    )
    def test_sanitize_raw_string_data(self, input_text, expected_contains, test_description):
        """Test _sanitize_raw_string_data with various input patterns."""

        result = self.data_sanitizer.sanitize(input_text)

        assert result == expected_contains, f"Failed {test_description}: Expected '{expected_contains}', got '{result}'"
