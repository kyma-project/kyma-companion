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

FUNCTION_NO_REPLICAS = """
{
    "apiVersion": "serverless.kyma-project.io/v1alpha2",
    "items": [
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
                            "name": "func1",
                            "namespace": "kyma-serverless-function-no-replicas"
                        },
                        "spec": {
                            "replicas": 0,
                            "runtime": "nodejs20",
                            "source": {
                                "inline": {
                                    "source": "module.exports = {\n  main: function(event, context) {\n    return 'Hello World!'\n  }\n}\n"
                                }
                            }
                        }
                    }
                },
                "creationTimestamp": "2024-09-12T14:19:18Z",
                "generation": 1,
                "managedFields": [
                    {
                        "apiVersion": "serverless.kyma-project.io/v1alpha2",
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
                                "f:replicas": {},
                                "f:runtime": {},
                                "f:source": {
                                    ".": {},
                                    "f:inline": {
                                        ".": {},
                                        "f:source": {}
                                    }
                                }
                            }
                        },
                        "manager": "kubectl-client-side-apply",
                        "operation": "Update",
                        "time": "2024-09-12T14:19:18Z"
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
                                "f:runtime": {},
                                "f:runtimeImage": {}
                            }
                        },
                        "manager": "manager",
                        "operation": "Update",
                        "subresource": "status",
                        "time": "2024-11-08T04:20:26Z"
                    }
                ],
                "name": "func1",
                "namespace": "kyma-serverless-function-no-replicas",
                "resourceVersion": "74099060",
                "uid": "3410fa58-c6ec-4f06-99c3-4ed7e0b0e328"
            },
            "spec": {
                "replicas": 0,
                "runtime": "nodejs20",
                "source": {
                    "inline": {
                        "source": "module.exports = {\n  main: function(event, context) {\n    return 'Hello World!'\n  }\n}\n"
                    }
                }
            },
            "status": {
                "buildResourceProfile": "slow",
                "conditions": [
                    {
                        "lastTransitionTime": "2024-11-08T04:20:26Z",
                        "message": "Deployment func1-hklrv is ready",
                        "reason": "DeploymentReady",
                        "status": "True",
                        "type": "Running"
                    },
                    {
                        "lastTransitionTime": "2024-09-12T14:19:43Z",
                        "message": "Job func1-build-v4t2n finished",
                        "reason": "JobFinished",
                        "status": "True",
                        "type": "BuildReady"
                    },
                    {
                        "lastTransitionTime": "2024-09-12T14:19:18Z",
                        "message": "ConfigMap func1-strr9 created",
                        "reason": "ConfigMapCreated",
                        "status": "True",
                        "type": "ConfigurationReady"
                    }
                ],
                "functionResourceProfile": "XS",
                "podSelector": "serverless.kyma-project.io/function-name=func1,serverless.kyma-project.io/managed-by=function-controller,serverless.kyma-project.io/resource=deployment,serverless.kyma-project.io/uuid=3410fa58-c6ec-4f06-99c3-4ed7e0b0e328",
                "runtime": "nodejs20",
                "runtimeImage": "europe-docker.pkg.dev/kyma-project/prod/function-runtime-nodejs20:1.5.1"
            }
        }
    ],
    "kind": "FunctionList",
    "metadata": {
        "continue": "",
        "resourceVersion": "74100905"
    }
}
"""

KYMADOC_FOR_SERVERLESS_FUNCTION_POD_NOT_READY = """
# Failing Function Container  
## Symptom  
The container suddenly fails when you use the `kyma run function` command with these flags:  
- `runtime=nodejs20`
- `debug=true`
- `hot-deploy=true`  
In such a case, you can see the `[nodemon] app crashed` message in the container's logs.  
## Remedy  
If you use Kyma in Kubernetes, Kubernetes itself should run the Function in the container.
If you use Kyma without Kubernetes, you have to rerun the container yourself.
# Serverless Architecture  
Serverless relies heavily on Kubernetes resources. It uses [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/), [Services](https://kubernetes.io/docs/concepts/services-networking/service/) and [HorizontalPodAutoscalers](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) to deploy and manage Functions, and [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/) to create Docker images. See how these and other resources process a Function within a Kyma cluster:  
![Serverless architecture](../../assets/svls-architecture.svg)  
> [!WARNING]
> Serverless imposes some requirements on the setup of namespaces. For example, if you apply custom [LimitRanges](https://kubernetes.io/docs/concepts/policy/limit-range/) for a new namespace, they must be higher than or equal to the limits for building Jobs' resources.  
1. Create a Function either through the UI or by applying a Function custom resource (CR). This CR contains the Function definition (business logic that you want to execute) and information on the environment on which it should run.  
2. Before the Function can be saved or modified, it is first updated and then verified by the defaulting and validation webhooks respectively.  
3. Function Controller (FC) detects the new, validated Function CR.  
4. FC creates a ConfigMap with the Function definition.  
5. Based on the ConfigMap, FC creates a Kubernetes Job that triggers the creation of a Function image.  
6. The Job creates a Pod which builds the production Docker image based on the Function's definition. The Job then pushes this image to a Docker registry.  
7. FC monitors the Job status. When the image creation finishes successfully, FC creates a Deployment that uses the newly built image.  
8. FC creates a Service that points to the Deployment.  
9. FC creates a HorizontalPodAutoscaler that automatically scales the number of Pods in the Deployment based on the observed CPU utilization.  
10. FC waits for the Deployment to become ready.
# Failure to Build Functions  
## Symptom  
You have issues when building your Function.  
## Cause  
In its default configuration, Serverless uses persistent volumes as the internal registry to store Docker images for Functions. The default storage size of such a volume is 20 GB. When this storage becomes full, you will have issues with building your Functions.  
## Remedy  
As a workaround, increase the default capacity up to a maximum of 100 GB by editing the `serverless-docker-registry` PersistentVolumeClaim (PVC) object on your cluster.  
1. Edit the `serverless-docker-registry` PVC:  
```bash
kubectl edit pvc -n kyma-system serverless-docker-registry
```  
2. Change the value of **spec.resources.requests.storage** to higher, such as 30 GB, to increase the PVC capacity:  
```yaml
...
spec:
resources:
requests:
storage: 30Gi
```  
3. Save the changes and wait for a few minutes. Use this command to check if the **CAPACITY** of the `serverless-docker-registry` PVC has changed as expected:  
```bash
kubectl get pvc serverless-docker-registry -n kyma-system
```  
You should get the following result:  
```bash
NAME                        STATUS   VOLUME                                    CAPACITY   ACCESS MODES   STORAGECLASS   AGE
serverless-docker-registry  Bound    pvc-a69b96hc-ahbc-k85d-0gh6-19gkcr4yns4k  30Gi       RWO            standard       23d
```  
If the value of the storage does not change, restart the Pod to which this PVC is bound to finish the volume resize.  
To do this, follow these steps:  
1. List all available Pods in the `kyma-system` namespace:  
```bash
kubectl get pods -n kyma-system
```  
2. Search for the Pod with the `serverless-docker-registry-{UNIQUE_ID}` name and delete it. See the example below:  
```bash
kubectl delete pod serverless-docker-registry-6869bd57dc-9tqxp -n kyma-system
```  
> [!WARNING]
> Do not remove Pods named `serverless-docker-registry-self-signed-cert-{UNIQUE_ID}`.  
3. Search for the `serverless-docker-registry` PVC again to check that the capacity was resized:  
```bash
kubectl get pvc serverless-docker-registry -n kyma-system
```
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

EXPECTED_SERVERLESS_FUNCTION_RESPONSE_NO_REPLICAS = """
The pod of the serverless Function is not ready because the Function has been configured with `replicas: 0`. This means that no pods are being created to run the Function.

Here is the relevant part of the Function configuration:
```yaml
spec:
  replicas: 0
  runtime: nodejs20
  source:
    inline:
      source: |
        module.exports = {
          main: function(event, context) {
            return 'Hello World!'
          }
        }
```

To resolve this issue, you need to update the Function configuration to set the `replicas` field to a value greater than 0. This will ensure that the necessary pods are created and the Function becomes ready.

You can update the Function configuration using the following command:
```bash
kubectl edit function func1 -n kyma-serverless-function-no-replicas
```

Change the `replicas` field to a value greater than 0, for example:
```yaml
spec:
  replicas: 1
```
"""
