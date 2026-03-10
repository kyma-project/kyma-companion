API_RULE_WITH_CONFLICT_ACCESS_STRATEGIES = """
"apiVersion": "gateway.kyma-project.io/v2",
"items": [
    {
        "apiVersion": "gateway.kyma-project.io/v2",
        "kind": "APIRule",
        "metadata": {
            "annotations": {
                "kubectl.kubernetes.io/last-applied-configuration": {
                    "apiVersion": "gateway.kyma-project.io/v2",
                    "kind": "APIRule",
                    "metadata": {
                        "annotations": {},
                        "name": "restapi",
                        "namespace": "kyma-app-apirule-broken"
                    },
                    "spec": {
                        "gateway": "kyma-system/kyma-gateway",
                        "hosts": ["kyma-app-apirule-broken.c-5cb6076.stage.kyma.ondemand.com"],
                        "rules": [
                            {
                                "noAuth": true,
                                "jwt": {
                                    "authentications": [
                                        {
                                            "issuer": "https://dev.kyma.local",
                                            "jwksUri": "https://dev.kyma.local/.well-known/jwks.json"
                                        }
                                    ]
                                },
                                "methods": [
                                    "GET",
                                    "POST"
                                ],
                                "path": "/.*",
                                "service": {
                                    "name": "restapi",
                                    "port": 80
                                }
                            }
                        ]
                    }
                }
            },
            "creationTimestamp": "2024-09-12T14:19:04Z",
            "finalizers": [
                "gateway.kyma-project.io/subresources"
            ],
            "generation": 1,
            "managedFields": [
                {
                    "apiVersion": "gateway.kyma-project.io/v2",
                    "fieldsType": "FieldsV1",
                    "fieldsV1": {
                        "f:metadata": {
                            "f:annotations": {
                                ".": {},
                                "f:kubectl.kubernetes.io/last-applied-configuration": {}
                            }
                        },
                        "f:spec": {
                            ".": {},
                            "f:gateway": {},
                            "f:hosts": {},
                            "f:rules": {}
                        }
                    },
                    "manager": "kubectl-client-side-apply",
                    "operation": "Update",
                    "time": "2024-09-12T14:19:04Z"
                },
                {
                    "apiVersion": "gateway.kyma-project.io/v2",
                    "fieldsType": "FieldsV1",
                    "fieldsV1": {
                        "f:metadata": {
                            "f:finalizers": {
                                ".": {},
                                "v:\"gateway.kyma-project.io/subresources\"": {}
                            }
                        }
                    },
                    "manager": "manager",
                    "operation": "Update",
                    "time": "2024-09-12T14:19:04Z"
                },
                {
                    "apiVersion": "gateway.kyma-project.io/v2",
                    "fieldsType": "FieldsV1",
                    "fieldsV1": {
                        "f:status": {
                            ".": {},
                            "f:state": {},
                            "f:description": {},
                            "f:lastProcessedTime": {},
                            "f:observedGeneration": {}
                        }
                    },
                    "manager": "manager",
                    "operation": "Update",
                    "subresource": "status",
                    "time": "2024-11-04T17:59:23Z"
                }
            ],
            "name": "restapi",
            "namespace": "kyma-app-apirule-broken",
            "resourceVersion": "71301490",
            "uid": "7bd25925-efc7-4f1c-a1f3-67cb45b585bc"
        },
        "spec": {
            "gateway": "kyma-system/kyma-gateway",
            "hosts": ["kyma-app-apirule-broken.c-5cb6076.stage.kyma.ondemand.com"],
            "rules": [
                {
                    "noAuth": true,
                    "jwt": {
                        "authentications": [
                            {
                                "issuer": "https://dev.kyma.local",
                                "jwksUri": "https://dev.kyma.local/.well-known/jwks.json"
                            }
                        ]
                    },
                    "methods": [
                        "GET",
                        "POST"
                    ],
                    "path": "/.*",
                    "service": {
                        "name": "restapi",
                        "port": 80
                    }
                }
            ]
        },
        "status": {
            "state": "Error",
            "description": "Multiple validation errors: \nAttribute \".spec.rules[0]\": noAuth and jwt cannot be used simultaneously on the same rule. Remove either noAuth or the jwt authenticator from the rule.",
            "lastProcessedTime": "2024-11-04T17:59:23Z",
            "observedGeneration": 1
        }
    }
],
"kind": "APIRuleList",
"metadata": {
    "continue": "",
    "resourceVersion": "71302033"
}
"""

KYMADOC_FOR_API_RULE_VALIDATION_ERROR = """
## Incompatible Authentication Methods
### Cause
The following APIRule (v2) has both `noAuth: true` and a `jwt` authenticator defined on the same rule:
```yaml
spec:
  rules:
  - path: /.*
    methods: ["GET"]
    noAuth: true
    jwt:
      authentications:
      - issuer: "https://example.com"
        jwksUri: "https://example.com/.well-known/jwks.json"
```
Combining `noAuth: true` with the `jwt` authenticator on the same rule is not supported. This results in the following error:
```
{"state": "Error", "description": "Attribute \".spec.rules[0]\": noAuth and jwt cannot be used simultaneously on the same rule."}
```
### Remedy
Choose exactly one authentication method per rule:
- Use `noAuth: true` for unauthenticated (open) access.
- Use `jwt` with `authentications` for JWT-protected access.
You cannot combine them on the same rule.
"""

EXPECTED_API_RULE_RESPONSE = """
The APIRule 'restapi' has a misconfiguration in its authentication setup. The error occurs because `noAuth: true` and a `jwt` authenticator are defined on the same rule, which is not allowed in APIRule v2.

The error message:
```
"noAuth and jwt cannot be used simultaneously on the same rule"
```

The current (incorrect) configuration on path `/.* `:
```yaml
rules:
- path: /.*
  noAuth: true          # conflicts with jwt below
  jwt:
    authentications:
    - issuer: "https://dev.kyma.local"
      jwksUri: "https://dev.kyma.local/.well-known/jwks.json"
```

To fix this, choose exactly one authentication method:

Option 1 — open access (no authentication):
```yaml
rules:
- path: /.*
  noAuth: true
```

Option 2 — JWT-protected access:
```yaml
rules:
- path: /.*
  jwt:
    authentications:
    - issuer: "https://dev.kyma.local"
      jwksUri: "https://dev.kyma.local/.well-known/jwks.json"
```
"""

EXPECTED_API_RULE_TOOL_CALL_RESPONSE = """
{
    "role": "assistant",
    "content": "",
    "additional_kwargs": {
        "refusal": null,
        "tool_calls": [
            {
                "id": "call_tbAMSFELnLfbU3VPvBT64Ona",
                "type": "function",
                "function": {
                    "name": "kyma_query_tool",
                    "arguments": {
                        "uri": "/apis/gateway.kyma-project.io/v2/namespaces/kyma-app-apirule-broken/apirules"
                    }
                }
            }
        ]
    }
}
"""

EXPECTED_API_RULE_DOC_SEARCH_TOOL_CALL_RESPONSE = """
{
    "refusal": null,
    "tool_calls": [
        {
            "id": "call_rlyq2ogbxzI8HaArhHYubnY2",
            "type": "function",
            "function": {
                "name": "search_kyma_doc_tool",
                "arguments": {
                    "query": "Diagnose API Rule issues"
                }
            }
        }
    ]
}"""
