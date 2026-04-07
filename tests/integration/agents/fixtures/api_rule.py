API_RULE_WITH_WRONG_ACCESS_STRATEGY = """
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
                        "hosts": [
                            "kyma-app-apirule-broken.c-5cb6076.stage.kyma.ondemand.com"
                        ],
                        "rules": [
                            {
                                "jwt": {
                                    "authentications": [
                                        {
                                            "issuer": "https://dev.kyma.local",
                                            "jwksUri": "https://dev.kyma.local/.well-known/jwks.json"
                                        }
                                    ]
                                },
                                "noAuth": true,
                                "methods": [
                                    "GET",
                                    "POST"
                                ],
                                "path": "/.*"
                            }
                        ],
                        "service": {
                            "name": "restapi",
                            "namespace": "kyma-app-apirule-broken",
                            "port": 80
                        }
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
                            "f:rules": {},
                            "f:service": {
                                ".": {},
                                "f:name": {},
                                "f:namespace": {},
                                "f:port": {}
                            }
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
            "hosts": [
                "kyma-app-apirule-broken.c-5cb6076.stage.kyma.ondemand.com"
            ],
            "rules": [
                {
                    "jwt": {
                        "authentications": [
                            {
                                "issuer": "https://dev.kyma.local",
                                "jwksUri": "https://dev.kyma.local/.well-known/jwks.json"
                            }
                        ]
                    },
                    "noAuth": true,
                    "methods": [
                        "GET",
                        "POST"
                    ],
                    "path": "/.*"
                }
            ],
            "service": {
                "name": "restapi",
                "namespace": "kyma-app-apirule-broken",
                "port": 80
            }
        },
        "status": {
            "state": "ERROR",
            "description": "Multiple validation errors: \nAttribute \".spec.rules[0]\": noAuth and jwt are mutually exclusive and cannot be used together on the same path",
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
## Unsupported Handlers' Combination
### Cause
The following APIRule has both `noAuth` and `jwt` defined on the same path:
```yaml
spec:
...
rules:
- path: /.*
methods: ["GET"]
noAuth: true
jwt:
  authentications:
  - issuer: https://dev.kyma.local
    jwksUri: https://dev.kyma.local/.well-known/jwks.json
```
The configuration in the above example is not supported. If an APIRule has both `noAuth` and `jwt` defined **on the same path**, the following `status` error appears:
```
{"state":"ERROR","description":"Attribute \".spec.rules[0]\": noAuth and jwt are mutually exclusive and cannot be used together on the same path"}
```
### Remedy
Decide on one configuration you want to use. You can either use `noAuth: true` to allow unauthenticated access to the specific path or restrict it using the JWT security token. Defining both configuration methods on the same path is not allowed.
"""

EXPECTED_API_RULE_RESPONSE = """
Looking at the APIRule configuration and the error message, there is a specific issue with the access configuration. The error occurs because you're trying to use both `noAuth` and `jwt` together, which is not allowed.

The error message clearly states:
- `noAuth` and `jwt` are mutually exclusive and cannot be used together on the same path

Here's what's wrong in the current configuration:
```yaml
rules:
- path: /.*
  noAuth: true
  jwt:
    authentications:
    - issuer: https://dev.kyma.local
      jwksUri: https://dev.kyma.local/.well-known/jwks.json
```

To fix this, you should choose only one access strategy.

```yaml
rules:
- path: /.*
  jwt:
    authentications:
    - issuer: https://dev.kyma.local
      jwksUri: https://dev.kyma.local/.well-known/jwks.json
```

OR

```yaml
rules:
- path: /.*
  noAuth: true
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
