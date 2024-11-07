API_RULE_WITH_WRONG_ACCESS_STRATEGY = """
"apiVersion": "gateway.kyma-project.io/v1beta1",
"items": [
    {
        "apiVersion": "gateway.kyma-project.io/v1beta1",
        "kind": "APIRule",
        "metadata": {
            "annotations": {
                "kubectl.kubernetes.io/last-applied-configuration": {
                    "apiVersion": "gateway.kyma-project.io/v1beta1",
                    "kind": "APIRule",
                    "metadata": {
                        "annotations": {},
                        "name": "restapi",
                        "namespace": "kyma-app-apirule-broken"
                    },
                    "spec": {
                        "gateway": "kyma-system/kyma-gateway",
                        "host": "kyma-app-apirule-broken.c-5cb6076.stage.kyma.ondemand.com",
                        "rules": [
                            {
                                "accessStrategies": [
                                    {
                                        "handler": "no_auth"
                                    },
                                    {
                                        "handler": "allow"
                                    }
                                ],
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
                    "apiVersion": "gateway.kyma-project.io/v1beta1",
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
                            "f:host": {},
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
                    "apiVersion": "gateway.kyma-project.io/v1beta1",
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
                    "apiVersion": "gateway.kyma-project.io/v1beta1",
                    "fieldsType": "FieldsV1",
                    "fieldsV1": {
                        "f:status": {
                            ".": {},
                            "f:APIRuleStatus": {
                                ".": {},
                                "f:code": {},
                                "f:desc": {}
                            },
                            "f:accessRuleStatus": {
                                ".": {},
                                "f:code": {}
                            },
                            "f:lastProcessedTime": {},
                            "f:observedGeneration": {},
                            "f:virtualServiceStatus": {
                                ".": {},
                                "f:code": {}
                            }
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
            "host": "kyma-app-apirule-broken.c-5cb6076.stage.kyma.ondemand.com",
            "rules": [
                {
                    "accessStrategies": [
                        {
                            "handler": "no_auth"
                        },
                        {
                            "handler": "allow"
                        }
                    ],
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
            "APIRuleStatus": {
                "code": "ERROR",
                "desc": "Multiple validation errors: \nAttribute \".spec.rules[0].accessStrategies.accessStrategies[1].handler\": allow access strategy is not allowed in combination with other access strategies\nAttribute \".spec.rules[0].accessStrategies.accessStrategies[0].handler\": no_auth access strategy is not allowed in combination with other access strategies"
            },
            "accessRuleStatus": {
                "code": "SKIPPED"
            },
            "lastProcessedTime": "2024-11-04T17:59:23Z",
            "observedGeneration": 1,
            "virtualServiceStatus": {
                "code": "SKIPPED"
            }
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
The following APIRule has both `allow` and `jwt` handlers defined on the same path:  
```yaml
spec:
...
rules:
- path: /.*
methods: ["GET"]
accessStrategies:
- handler: allow
- handler: jwt
config:
trusted_issuers: ["https://dev.kyma.local"]
```  
The handlers' combination in the above example is not supported. If an APIRule has an unsupported handlers' combination defined **on the same path**, the following `APIRuleStatus` error appears:  
```
{"code":"ERROR","desc":"Validation error: Attribute \".spec.rules[0].accessStrategies.accessStrategies[0].handler\": allow access strategy is not allowed in combination with other access strategies"}
```  
### Remedy  
Decide on one configuration you want to use. You can either `allow` access to the specific path or restrict it using the JWT security token. Defining both configuration methods on the same path is not allowed.
"""
