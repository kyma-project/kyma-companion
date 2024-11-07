SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR = """
{
    "apiVersion": "serverless.kyma-project.io/v1alpha2",
    "kind": "Function",
    "metadata": {
        "annotations": {
            "kubectl.kubernetes.io/last-applied-configuration": {
                "apiVersion": "serverless.kyma-project.io/v1alpha2",
                "kind": "Function",
                "metadata": {
                    "annotations": {},
                    "labels": {
                        "app": "restapi"
                    },
                    "name": "func1",
                    "namespace": "kyma-app-serverless-syntax-err"
                },
                "spec": {
                    "runtime": "nodejs20",
                    "source": {
                        "inline": {
                            "dependencies": {
                                "name": "func1",
                                "version": "1.0.0",
                                "dependencies": {}
                            },
                            "source": "module.exports = {\n  main: async function (event, context) {\n      // Return a response.\n      const now = new Dates();\n      const response = {\n      statusCode: 200,\n      result: {\n        message: 'Serverless function is up and running',\n        status: 'success',\n        utcDatetime: now\n      }\n    };\n    console.log('Response:', response);\n    return response;\n  }\n}\n"
                        }
                    }
                }
            }
        },
        "creationTimestamp": "2024-09-12T14:19:11Z",
        "generation": 1,
        "labels": {
            "app": "restapi"
        },
        "managedFields": [
            {
                "apiVersion": "serverless.kyma-project.io/v1alpha2",
                "fieldsType": "FieldsV1",
                "fieldsV1": {
                    "f:metadata": {
                        "f:annotations": {
                            ".": {},
                            "f:kubectl.kubernetes.io/last-applied-configuration": {}
                        },
                        "f:labels": {
                            ".": {},
                            "f:app": {}
                        }
                    },
                    "f:spec": {
                        ".": {},
                        "f:replicas": {},
                        "f:runtime": {},
                        "f:source": {
                            ".": {},
                            "f:inline": {
                                ".": {},
                                "f:dependencies": {},
                                "f:source": {}
                            }
                        }
                    }
                },
                "manager": "kubectl-client-side-apply",
                "operation": "Update",
                "time": "2024-09-12T14:19:11Z"
            },
            {
                "apiVersion": "serverless.kyma-project.io/v1alpha2",
                "fieldsType": "FieldsV1",
                "fieldsV1": {
                    "f:status": {
                        ".": {},
                        "f:buildResourceProfile": {},
                        "f:conditions": {},
                        "f:functionResourceProfile": {},
                        "f:podSelector": {},
                        "f:replicas": {},
                        "f:runtime": {},
                        "f:runtimeImage": {}
                    }
                },
                "manager": "manager",
                "operation": "Update",
                "subresource": "status",
                "time": "2024-11-05T16:07:09Z"
            }
        ],
        "name": "func1",
        "namespace": "kyma-app-serverless-syntax-err",
        "resourceVersion": "72068392",
        "uid": "23066ef7-548a-457b-b006-fae7c22604d2"
    },
    "spec": {
        "replicas": 1,
        "runtime": "nodejs20",
        "source": {
            "inline": {
                "dependencies": {
                    "name": "func1",
                    "version": "1.0.0",
                    "dependencies": {}
                },
                "source": "module.exports = {\n  main: async function (event, context) {\n      // Return a response.\n      const now = new Dates();\n      const response = {\n      statusCode: 200,\n      result: {\n        message: 'Serverless function is up and running',\n        status: 'success',\n        utcDatetime: now\n      }\n    };\n    console.log('Response:', response);\n    return response;\n  }\n}\n"
            }
        }
    },
    "status": {
        "buildResourceProfile": "slow",
        "conditions": [
            {
                "lastTransitionTime": "2024-11-05T16:07:09Z",
                "message": "Deployment func1-f2b6n is ready",
                "reason": "DeploymentReady",
                "status": "True",
                "type": "Running"
            },
            {
                "lastTransitionTime": "2024-09-12T14:19:44Z",
                "message": "Job func1-build-lwmrr finished",
                "reason": "JobFinished",
                "status": "True",
                "type": "BuildReady"
            },
            {
                "lastTransitionTime": "2024-09-12T14:19:11Z",
                "message": "Updated ConfigMap: \"func1-2tp95\"",
                "reason": "ConfigMapUpdated",
                "status": "True",
                "type": "ConfigurationReady"
            }
        ],
        "functionResourceProfile": "XS",
        "podSelector": "serverless.kyma-project.io/function-name=func1,serverless.kyma-project.io/managed-by=function-controller,serverless.kyma-project.io/resource=deployment,serverless.kyma-project.io/uuid=23066ef7-548a-457b-b006-fae7c22604d2",
        "replicas": 1,
        "runtime": "nodejs20",
        "runtimeImage": "europe-docker.pkg.dev/kyma-project/prod/function-runtime-nodejs20:1.5.1"
    }
}
"""

EXPECTED_SERVERLESS_FUNCTION_RESPONSE = """
The function fails because of an incorrect Date object constructor:

```javascript
const now = new Dates(); // Wrong
```

Should be:

```javascript
const now = new Date(); // Correct
```

Simply fix the constructor name from `Dates` to `Date` and the function will work properly.
"""