sample_pods_tool_response = """[
  {
    "metadata": {
      "name": "cert-manager-769fdd4544-tjwwk",
      "generateName": "cert-manager-769fdd4544-",
      "namespace": "cert-manager",
      "uid": "bc16e89f-ee05-4508-bde7-3ab7ed350eae",
      "resourceVersion": "230786573",
      "creationTimestamp": "2025-02-04T09:47:33Z",
      "labels": {
        "app": "cert-manager",
        "app.kubernetes.io/component": "controller",
        "app.kubernetes.io/instance": "cert-manager",
        "app.kubernetes.io/name": "cert-manager",
        "app.kubernetes.io/version": "v1.11.0",
        "pod-template-hash": "769fdd4544"
      },
      "annotations": {
        "cni.projectcalico.org/containerID": "453edc44cb3cd26186219e38ae8c025739feed05403d94bfc8fb3216c2437d5a",
        "cni.projectcalico.org/podIP": "100.96.1.30/32",
        "cni.projectcalico.org/podIPs": "100.96.1.30/32",
        "prometheus.io/path": "/metrics",
        "prometheus.io/port": "9402",
        "prometheus.io/scrape": "true"
      },
      "ownerReferences": [
        {
          "apiVersion": "apps/v1",
          "kind": "ReplicaSet",
          "name": "cert-manager-769fdd4544",
          "uid": "c3d86149-e05a-4bd8-964d-5c51c603bc17",
          "controller": true,
          "blockOwnerDeletion": true
        }
      ],
      "managedFields": [
        {
          "manager": "kube-controller-manager",
          "operation": "Update",
          "apiVersion": "v1",
          "time": "2025-02-04T09:47:33Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:annotations": {
                ".": {},
                "f:prometheus.io/path": {},
                "f:prometheus.io/port": {},
                "f:prometheus.io/scrape": {}
              },
              "f:generateName": {},
              "f:labels": {
                ".": {},
                "f:app": {},
                "f:app.kubernetes.io/component": {},
                "f:app.kubernetes.io/instance": {},
                "f:app.kubernetes.io/name": {},
                "f:app.kubernetes.io/version": {},
                "f:pod-template-hash": {}
              },
              "f:ownerReferences": {
                ".": {},
                "k:{'uid':'c3d86149-e05a-4bd8-964d-5c51c603bc17'}": {}
              }
            },
            "f:spec": {
              "f:containers": {
                "k:{'name':'cert-manager-controller'}": "[REDACTED]"
              },
              "f:dnsPolicy": {},
              "f:enableServiceLinks": {},
              "f:nodeSelector": {},
              "f:restartPolicy": {},
              "f:schedulerName": {},
              "f:securityContext": {
                ".": {},
                "f:runAsNonRoot": {},
                "f:seccompProfile": {
                  ".": {},
                  "f:type": {}
                }
              },
              "f:serviceAccount": {},
              "f:serviceAccountName": {},
              "f:terminationGracePeriodSeconds": {}
            }
          }
        },
        {
          "manager": "calico",
          "operation": "Update",
          "apiVersion": "v1",
          "time": "2025-02-04T09:47:34Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:annotations": {
                "f:cni.projectcalico.org/containerID": {},
                "f:cni.projectcalico.org/podIP": {},
                "f:cni.projectcalico.org/podIPs": {}
              }
            }
          },
          "subresource": "status"
        },
        {
          "manager": "kubelet",
          "operation": "Update",
          "apiVersion": "v1",
          "time": "2025-05-16T23:55:31Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:status": {
              "f:conditions": {
                "k:{'type':'ContainersReady'}": {
                  ".": {},
                  "f:lastProbeTime": {},
                  "f:lastTransitionTime": {},
                  "f:status": {},
                  "f:type": {}
                },
                "k:{'type':'Initialized'}": {
                  ".": {},
                  "f:lastProbeTime": {},
                  "f:lastTransitionTime": {},
                  "f:status": {},
                  "f:type": {}
                },
                "k:{'type':'PodReadyToStartContainers'}": {
                  ".": {},
                  "f:lastProbeTime": {},
                  "f:lastTransitionTime": {},
                  "f:status": {},
                  "f:type": {}
                },
                "k:{'type':'Ready'}": {
                  ".": {},
                  "f:lastProbeTime": {},
                  "f:lastTransitionTime": {},
                  "f:status": {},
                  "f:type": {}
                }
              },
              "f:containerStatuses": {},
              "f:hostIP": {},
              "f:hostIPs": {},
              "f:phase": {},
              "f:podIP": {},
              "f:podIPs": {
                ".": {},
                "k:{'ip':'100.96.1.30'}": {
                  ".": {},
                  "f:ip": {}
                }
              },
              "f:startTime": {}
            }
          },
          "subresource": "status"
        }
      ]
    },
    "spec": {
      "volumes": [
        {
          "name": "kube-api-access-fwsxg",
          "projected": {
            "sources": [
              {
                "serviceAccountToken": "[REDACTED]"
              },
              {
                "configMap": {
                  "name": "kube-root-ca.crt",
                  "items": [
                    {
                      "key": "[REDACTED]",
                      "path": "ca.crt"
                    }
                  ]
                }
              },
              {
                "downwardAPI": {
                  "items": [
                    {
                      "path": "namespace",
                      "fieldRef": {
                        "apiVersion": "v1",
                        "fieldPath": "metadata.namespace"
                      }
                    }
                  ]
                }
              }
            ],
            "defaultMode": 420
          }
        }
      ],
      "containers": [
        {
          "name": "cert-manager-controller",
          "image": "quay.io/jetstack/cert-manager-controller:v1.11.0",
          "args": [
            "--v=2",
            "--cluster-resource-namespace=$(POD_NAMESPACE)",
            "--leader-election-namespace=kube-system",
            "--acme-http01-solver-image=quay.io/jetstack/cert-manager-acmesolver:v1.11.0",
            "--max-concurrent-challenges=60"
          ],
          "ports": [
            {
              "name": "http-metrics",
              "containerPort": 9402,
              "protocol": "TCP"
            }
          ],
          "env": [
            {
              "name": "POD_NAMESPACE",
              "valueFrom": {
                "fieldRef": {
                  "apiVersion": "v1",
                  "fieldPath": "metadata.namespace"
                }
              }
            },
            {
              "name": "KUBERNETES_SERVICE_HOST",
              "value": "api.comp-tests-0.kymatunas.internal.canary.k8s.ondemand.com"
            }
          ],
          "resources": {},
          "volumeMounts": [
            {
              "name": "kube-api-access-fwsxg",
              "readOnly": true,
              "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount"
            }
          ],
          "terminationMessagePath": "/dev/termination-log",
          "terminationMessagePolicy": "File",
          "imagePullPolicy": "IfNotPresent",
          "securityContext": {
            "capabilities": {
              "drop": [
                "ALL"
              ]
            },
            "allowPrivilegeEscalation": false
          }
        }
      ],
      "restartPolicy": "Always",
      "terminationGracePeriodSeconds": 30,
      "dnsPolicy": "ClusterFirst",
      "nodeSelector": {
        "kubernetes.io/os": "linux"
      },
      "serviceAccountName": "cert-manager",
      "serviceAccount": "cert-manager",
      "nodeName": "ip-10-250-0-143.eu-west-1.compute.internal",
      "securityContext": {
        "runAsNonRoot": true,
        "seccompProfile": {
          "type": "RuntimeDefault"
        }
      },
      "schedulerName": "default-scheduler",
      "tolerations": [
        {
          "key": "[REDACTED]",
          "operator": "Exists",
          "effect": "NoExecute",
          "tolerationSeconds": 300
        },
        {
          "key": "[REDACTED]",
          "operator": "Exists",
          "effect": "NoExecute",
          "tolerationSeconds": 300
        }
      ],
      "priority": 0,
      "enableServiceLinks": true,
      "preemptionPolicy": "PreemptLowerPriority"
    },
    "status": {
      "phase": "Running",
      "conditions": [
        {
          "type": "PodReadyToStartContainers",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-02-04T09:47:34Z"
        },
        {
          "type": "Initialized",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-02-04T09:47:34Z"
        },
        {
          "type": "Ready",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-05-16T23:55:13Z"
        },
        {
          "type": "ContainersReady",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-05-16T23:55:13Z"
        },
        {
          "type": "PodScheduled",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-02-04T09:47:34Z"
        }
      ],
      "hostIP": "10.250.0.143",
      "hostIPs": [
        {
          "ip": "10.250.0.143"
        }
      ],
      "podIP": "100.96.1.30",
      "podIPs": [
        {
          "ip": "100.96.1.30"
        }
      ],
      "startTime": "2025-02-04T09:47:34Z",
      "containerStatuses": [
        {
          "name": "cert-manager-controller",
          "state": {
            "running": {
              "startedAt": "2025-05-16T23:55:13Z"
            }
          },
          "lastState": {
            "terminated": {
              "exitCode": 1,
              "reason": "Error",
              "startedAt": "2025-05-16T21:31:05Z",
              "finishedAt": "2025-05-16T23:55:12Z",
              "containerID": "containerd://3fd7bc427f35825baee761389cdd73b27b9f4bdba0087dafea2181671d9264f6"
            }
          },
          "ready": true,
          "restartCount": 63,
          "image": "quay.io/jetstack/cert-manager-controller:v1.11.0",
          "imageID": "quay.io/jetstack/cert-manager-controller@sha256:d429b6d696e0ef47cff1d15241c6ffaac351e38ac22664b82fafa771d615b89a",
          "containerID": "containerd://e203fc90675239475f01093c280a03f4526fb4341449d9a1ce82af920b59fe4f",
          "started": true
        }
      ],
      "qosClass": "BestEffort"
    }
  },
  {
    "metadata": {
      "name": "cert-manager-cainjector-56ccdfdd58-rsr4w",
      "generateName": "cert-manager-cainjector-56ccdfdd58-",
      "namespace": "cert-manager",
      "uid": "a554073c-db3e-4378-ac95-73ed3a446a63",
      "resourceVersion": "230704835",
      "creationTimestamp": "2025-02-04T09:47:33Z",
      "labels": {
        "app": "cainjector",
        "app.kubernetes.io/component": "cainjector",
        "app.kubernetes.io/instance": "cert-manager",
        "app.kubernetes.io/name": "cainjector",
        "app.kubernetes.io/version": "v1.11.0",
        "pod-template-hash": "56ccdfdd58"
      },
      "annotations": {
        "cni.projectcalico.org/containerID": "7863e5cf899ffbca8127b87875bcf5d3d76745eeaaf4fcfe24e085472fd66951",
        "cni.projectcalico.org/podIP": "100.96.1.32/32",
        "cni.projectcalico.org/podIPs": "100.96.1.32/32"
      },
      "ownerReferences": [
        {
          "apiVersion": "apps/v1",
          "kind": "ReplicaSet",
          "name": "cert-manager-cainjector-56ccdfdd58",
          "uid": "035b5dd1-ec54-4a93-9d24-107ecee0ffb3",
          "controller": true,
          "blockOwnerDeletion": true
        }
      ],
      "managedFields": [
        {
          "manager": "kube-controller-manager",
          "operation": "Update",
          "apiVersion": "v1",
          "time": "2025-02-04T09:47:33Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:generateName": {},
              "f:labels": {
                ".": {},
                "f:app": {},
                "f:app.kubernetes.io/component": {},
                "f:app.kubernetes.io/instance": {},
                "f:app.kubernetes.io/name": {},
                "f:app.kubernetes.io/version": {},
                "f:pod-template-hash": {}
              },
              "f:ownerReferences": {
                ".": {},
                "k:{'uid':'035b5dd1-ec54-4a93-9d24-107ecee0ffb3'}": {}
              }
            },
            "f:spec": {
              "f:containers": {
                "k:{'name':'cert-manager-cainjector'}": "[REDACTED]"
              },
              "f:dnsPolicy": {},
              "f:enableServiceLinks": {},
              "f:nodeSelector": {},
              "f:restartPolicy": {},
              "f:schedulerName": {},
              "f:securityContext": {
                ".": {},
                "f:runAsNonRoot": {},
                "f:seccompProfile": {
                  ".": {},
                  "f:type": {}
                }
              },
              "f:serviceAccount": {},
              "f:serviceAccountName": {},
              "f:terminationGracePeriodSeconds": {}
            }
          }
        },
        {
          "manager": "calico",
          "operation": "Update",
          "apiVersion": "v1",
          "time": "2025-02-04T09:47:34Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:annotations": {
                ".": {},
                "f:cni.projectcalico.org/containerID": {},
                "f:cni.projectcalico.org/podIP": {},
                "f:cni.projectcalico.org/podIPs": {}
              }
            }
          },
          "subresource": "status"
        },
        {
          "manager": "kubelet",
          "operation": "Update",
          "apiVersion": "v1",
          "time": "2025-05-16T21:31:32Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:status": {
              "f:conditions": {
                "k:{'type':'ContainersReady'}": {
                  ".": {},
                  "f:lastProbeTime": {},
                  "f:lastTransitionTime": {},
                  "f:status": {},
                  "f:type": {}
                },
                "k:{'type':'Initialized'}": {
                  ".": {},
                  "f:lastProbeTime": {},
                  "f:lastTransitionTime": {},
                  "f:status": {},
                  "f:type": {}
                },
                "k:{'type':'PodReadyToStartContainers'}": {
                  ".": {},
                  "f:lastProbeTime": {},
                  "f:lastTransitionTime": {},
                  "f:status": {},
                  "f:type": {}
                },
                "k:{'type':'Ready'}": {
                  ".": {},
                  "f:lastProbeTime": {},
                  "f:lastTransitionTime": {},
                  "f:status": {},
                  "f:type": {}
                }
              },
              "f:containerStatuses": {},
              "f:hostIP": {},
              "f:hostIPs": {},
              "f:phase": {},
              "f:podIP": {},
              "f:podIPs": {
                ".": {},
                "k:{'ip':'100.96.1.32'}": {
                  ".": {},
                  "f:ip": {}
                }
              },
              "f:startTime": {}
            }
          },
          "subresource": "status"
        }
      ]
    },
    "spec": {
      "volumes": [
        {
          "name": "kube-api-access-mdd7h",
          "projected": {
            "sources": [
              {
                "serviceAccountToken": "[REDACTED]"
              },
              {
                "configMap": {
                  "name": "kube-root-ca.crt",
                  "items": [
                    {
                      "key": "[REDACTED]",
                      "path": "ca.crt"
                    }
                  ]
                }
              },
              {
                "downwardAPI": {
                  "items": [
                    {
                      "path": "namespace",
                      "fieldRef": {
                        "apiVersion": "v1",
                        "fieldPath": "metadata.namespace"
                      }
                    }
                  ]
                }
              }
            ],
            "defaultMode": 420
          }
        }
      ],
      "containers": [
        {
          "name": "cert-manager-cainjector",
          "image": "quay.io/jetstack/cert-manager-cainjector:v1.11.0",
          "args": [
            "--v=2",
            "--leader-election-namespace=kube-system"
          ],
          "env": [
            {
              "name": "POD_NAMESPACE",
              "valueFrom": {
                "fieldRef": {
                  "apiVersion": "v1",
                  "fieldPath": "metadata.namespace"
                }
              }
            },
            {
              "name": "KUBERNETES_SERVICE_HOST",
              "value": "api.comp-tests-0.kymatunas.internal.canary.k8s.ondemand.com"
            }
          ],
          "resources": {},
          "volumeMounts": [
            {
              "name": "kube-api-access-mdd7h",
              "readOnly": true,
              "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount"
            }
          ],
          "terminationMessagePath": "/dev/termination-log",
          "terminationMessagePolicy": "File",
          "imagePullPolicy": "IfNotPresent",
          "securityContext": {
            "capabilities": {
              "drop": [
                "ALL"
              ]
            },
            "allowPrivilegeEscalation": false
          }
        }
      ],
      "restartPolicy": "Always",
      "terminationGracePeriodSeconds": 30,
      "dnsPolicy": "ClusterFirst",
      "nodeSelector": {
        "kubernetes.io/os": "linux"
      },
      "serviceAccountName": "cert-manager-cainjector",
      "serviceAccount": "cert-manager-cainjector",
      "nodeName": "ip-10-250-0-143.eu-west-1.compute.internal",
      "securityContext": {
        "runAsNonRoot": true,
        "seccompProfile": {
          "type": "RuntimeDefault"
        }
      },
      "schedulerName": "default-scheduler",
      "tolerations": [
        {
          "key": "[REDACTED]",
          "operator": "Exists",
          "effect": "NoExecute",
          "tolerationSeconds": 300
        },
        {
          "key": "[REDACTED]",
          "operator": "Exists",
          "effect": "NoExecute",
          "tolerationSeconds": 300
        }
      ],
      "priority": 0,
      "enableServiceLinks": true,
      "preemptionPolicy": "PreemptLowerPriority"
    },
    "status": {
      "phase": "Running",
      "conditions": [
        {
          "type": "PodReadyToStartContainers",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-02-04T09:47:34Z"
        },
        {
          "type": "Initialized",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-02-04T09:47:34Z"
        },
        {
          "type": "Ready",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-05-16T21:31:32Z"
        },
        {
          "type": "ContainersReady",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-05-16T21:31:32Z"
        },
        {
          "type": "PodScheduled",
          "status": "True",
          "lastProbeTime": null,
          "lastTransitionTime": "2025-02-04T09:47:34Z"
        }
      ],
      "hostIP": "10.250.0.143",
      "hostIPs": [
        {
          "ip": "10.250.0.143"
        }
      ],
      "podIP": "100.96.1.32",
      "podIPs": [
        {
          "ip": "100.96.1.32"
        }
      ],
      "startTime": "2025-02-04T09:47:34Z",
      "containerStatuses": [
        {
          "name": "cert-manager-cainjector",
          "state": {
            "running": {
              "startedAt": "2025-05-16T21:31:31Z"
            }
          },
          "lastState": {
            "terminated": {
              "exitCode": 1,
              "reason": "Error",
              "startedAt": "2025-05-16T21:31:05Z",
              "finishedAt": "2025-05-16T21:31:15Z",
              "containerID": "containerd://69dbdda3e1b13f305b4ab2fced02de9ccdfd47a790374c4028824554480f1a71"
            }
          },
          "ready": true,
          "restartCount": 113,
          "image": "quay.io/jetstack/cert-manager-cainjector:v1.11.0",
          "imageID": "quay.io/jetstack/cert-manager-cainjector@sha256:5c3eb25b085443b83586a98a1ae07f8364461dfca700e950c30f585efb7474ba",
          "containerID": "containerd://9cf4de58ae04e3ce55c835c70e03ce3dd9a1e4d75fa856cf1eed1684abca6768",
          "started": true
        }
      ],
      "qosClass": "BestEffort"
    }
  }]"""


sample_deployment_tool_response = """[
  {
    "metadata": {
      "name": "cert-manager",
      "namespace": "cert-manager",
      "uid": "3ad6e1c7-776a-4aea-866e-8107125e772f",
      "resourceVersion": "187977571",
      "generation": 1,
      "creationTimestamp": "2025-02-04T09:47:33Z",
      "labels": {
        "app": "cert-manager",
        "app.kubernetes.io/component": "controller",
        "app.kubernetes.io/instance": "cert-manager",
        "app.kubernetes.io/name": "cert-manager",
        "app.kubernetes.io/version": "v1.11.0"
      },
      "annotations": {
        "deployment.kubernetes.io/revision": "1"
      },
      "managedFields": [
        {
          "manager": "kyma",
          "operation": "Apply",
          "apiVersion": "apps/v1",
          "time": "2025-02-04T09:47:33Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:labels": {
                "f:app": {},
                "f:app.kubernetes.io/component": {},
                "f:app.kubernetes.io/instance": {},
                "f:app.kubernetes.io/name": {},
                "f:app.kubernetes.io/version": {}
              }
            },
            "f:spec": {
              "f:replicas": {},
              "f:selector": {},
              "f:strategy": {},
              "f:template": {
                "f:metadata": {
                  "f:annotations": {
                    "f:prometheus.io/path": {},
                    "f:prometheus.io/port": {},
                    "f:prometheus.io/scrape": {}
                  },
                  "f:creationTimestamp": {},
                  "f:labels": {
                    "f:app": {},
                    "f:app.kubernetes.io/component": {},
                    "f:app.kubernetes.io/instance": {},
                    "f:app.kubernetes.io/name": {},
                    "f:app.kubernetes.io/version": {}
                  }
                },
                "f:spec": {
                  "f:containers": {
                    "k:{'name':'cert-manager-controller'}": "[REDACTED]"
                  },
                  "f:nodeSelector": {},
                  "f:securityContext": {
                    "f:runAsNonRoot": {},
                    "f:seccompProfile": {
                      "f:type": {}
                    }
                  },
                  "f:serviceAccountName": {}
                }
              }
            }
          }
        },
        {
          "manager": "kube-controller-manager",
          "operation": "Update",
          "apiVersion": "apps/v1",
          "time": "2025-03-26T03:57:49Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:annotations": {
                ".": {},
                "f:deployment.kubernetes.io/revision": {}
              }
            },
            "f:status": {
              "f:availableReplicas": {},
              "f:conditions": {
                ".": {},
                "k:{'type':'Available'}": {
                  ".": {},
                  "f:lastTransitionTime": {},
                  "f:lastUpdateTime": {},
                  "f:message": {},
                  "f:reason": {},
                  "f:status": {},
                  "f:type": {}
                },
                "k:{'type':'Progressing'}": {
                  ".": {},
                  "f:lastTransitionTime": {},
                  "f:lastUpdateTime": {},
                  "f:message": {},
                  "f:reason": {},
                  "f:status": {},
                  "f:type": {}
                }
              },
              "f:observedGeneration": {},
              "f:readyReplicas": {},
              "f:replicas": {},
              "f:updatedReplicas": {}
            }
          },
          "subresource": "status"
        }
      ]
    },
    "spec": {
      "replicas": 1,
      "selector": {
        "matchLabels": {
          "app.kubernetes.io/component": "controller",
          "app.kubernetes.io/instance": "cert-manager",
          "app.kubernetes.io/name": "cert-manager"
        }
      },
      "template": {
        "metadata": {
          "creationTimestamp": null,
          "labels": {
            "app": "cert-manager",
            "app.kubernetes.io/component": "controller",
            "app.kubernetes.io/instance": "cert-manager",
            "app.kubernetes.io/name": "cert-manager",
            "app.kubernetes.io/version": "v1.11.0"
          },
          "annotations": {
            "prometheus.io/path": "/metrics",
            "prometheus.io/port": "9402",
            "prometheus.io/scrape": "true"
          }
        },
        "spec": {
          "containers": [
            {
              "name": "cert-manager-controller",
              "image": "quay.io/jetstack/cert-manager-controller:v1.11.0",
              "args": [
                "--v=2",
                "--cluster-resource-namespace=$(POD_NAMESPACE)",
                "--leader-election-namespace=kube-system",
                "--acme-http01-solver-image=quay.io/jetstack/cert-manager-acmesolver:v1.11.0",
                "--max-concurrent-challenges=60"
              ],
              "ports": [
                {
                  "name": "http-metrics",
                  "containerPort": 9402,
                  "protocol": "TCP"
                }
              ],
              "env": [
                {
                  "name": "POD_NAMESPACE",
                  "valueFrom": {
                    "fieldRef": {
                      "apiVersion": "v1",
                      "fieldPath": "metadata.namespace"
                    }
                  }
                }
              ],
              "resources": {},
              "terminationMessagePath": "/dev/termination-log",
              "terminationMessagePolicy": "File",
              "imagePullPolicy": "IfNotPresent",
              "securityContext": {
                "capabilities": {
                  "drop": [
                    "ALL"
                  ]
                },
                "allowPrivilegeEscalation": false
              }
            }
          ],
          "restartPolicy": "Always",
          "terminationGracePeriodSeconds": 30,
          "dnsPolicy": "ClusterFirst",
          "nodeSelector": {
            "kubernetes.io/os": "linux"
          },
          "serviceAccountName": "cert-manager",
          "serviceAccount": "cert-manager",
          "securityContext": {
            "runAsNonRoot": true,
            "seccompProfile": {
              "type": "RuntimeDefault"
            }
          },
          "schedulerName": "default-scheduler"
        }
      },
      "strategy": {
        "type": "RollingUpdate",
        "rollingUpdate": {
          "maxUnavailable": "25%",
          "maxSurge": "25%"
        }
      },
      "revisionHistoryLimit": 10,
      "progressDeadlineSeconds": 600
    },
    "status": {
      "observedGeneration": 1,
      "replicas": 1,
      "updatedReplicas": 1,
      "readyReplicas": 1,
      "availableReplicas": 1,
      "conditions": [
        {
          "type": "Progressing",
          "status": "True",
          "lastUpdateTime": "2025-02-04T09:47:34Z",
          "lastTransitionTime": "2025-02-04T09:47:33Z",
          "reason": "NewReplicaSetAvailable",
          "message": "ReplicaSet 'cert-manager-769fdd4544' has successfully progressed."
        },
        {
          "type": "Available",
          "status": "True",
          "lastUpdateTime": "2025-03-26T03:57:49Z",
          "lastTransitionTime": "2025-03-26T03:57:49Z",
          "reason": "MinimumReplicasAvailable",
          "message": "Deployment has minimum availability."
        }
      ]
    }
  },
  {
    "metadata": {
      "name": "cert-manager-cainjector",
      "namespace": "cert-manager",
      "uid": "72c789ff-853b-4f2a-a572-1d1f79211e92",
      "resourceVersion": "189143297",
      "generation": 1,
      "creationTimestamp": "2025-02-04T09:47:33Z",
      "labels": {
        "app": "cainjector",
        "app.kubernetes.io/component": "cainjector",
        "app.kubernetes.io/instance": "cert-manager",
        "app.kubernetes.io/name": "cainjector",
        "app.kubernetes.io/version": "v1.11.0"
      },
      "annotations": {
        "deployment.kubernetes.io/revision": "1"
      },
      "managedFields": [
        {
          "manager": "kyma",
          "operation": "Apply",
          "apiVersion": "apps/v1",
          "time": "2025-02-04T09:47:33Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:labels": {
                "f:app": {},
                "f:app.kubernetes.io/component": {},
                "f:app.kubernetes.io/instance": {},
                "f:app.kubernetes.io/name": {},
                "f:app.kubernetes.io/version": {}
              }
            },
            "f:spec": {
              "f:replicas": {},
              "f:selector": {},
              "f:strategy": {},
              "f:template": {
                "f:metadata": {
                  "f:creationTimestamp": {},
                  "f:labels": {
                    "f:app": {},
                    "f:app.kubernetes.io/component": {},
                    "f:app.kubernetes.io/instance": {},
                    "f:app.kubernetes.io/name": {},
                    "f:app.kubernetes.io/version": {}
                  }
                },
                "f:spec": {
                  "f:containers": {
                    "k:{'name':'cert-manager-cainjector'}": "[REDACTED]"
                  },
                  "f:nodeSelector": {},
                  "f:securityContext": {
                    "f:runAsNonRoot": {},
                    "f:seccompProfile": {
                      "f:type": {}
                    }
                  },
                  "f:serviceAccountName": {}
                }
              }
            }
          }
        },
        {
          "manager": "kube-controller-manager",
          "operation": "Update",
          "apiVersion": "apps/v1",
          "time": "2025-03-27T14:05:42Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:annotations": {
                ".": {},
                "f:deployment.kubernetes.io/revision": {}
              }
            },
            "f:status": {
              "f:availableReplicas": {},
              "f:conditions": {
                ".": {},
                "k:{'type':'Available'}": {
                  ".": {},
                  "f:lastTransitionTime": {},
                  "f:lastUpdateTime": {},
                  "f:message": {},
                  "f:reason": {},
                  "f:status": {},
                  "f:type": {}
                },
                "k:{'type':'Progressing'}": {
                  ".": {},
                  "f:lastTransitionTime": {},
                  "f:lastUpdateTime": {},
                  "f:message": {},
                  "f:reason": {},
                  "f:status": {},
                  "f:type": {}
                }
              },
              "f:observedGeneration": {},
              "f:readyReplicas": {},
              "f:replicas": {},
              "f:updatedReplicas": {}
            }
          },
          "subresource": "status"
        }
      ]
    },
    "spec": {
      "replicas": 1,
      "selector": {
        "matchLabels": {
          "app.kubernetes.io/component": "cainjector",
          "app.kubernetes.io/instance": "cert-manager",
          "app.kubernetes.io/name": "cainjector"
        }
      },
      "template": {
        "metadata": {
          "creationTimestamp": null,
          "labels": {
            "app": "cainjector",
            "app.kubernetes.io/component": "cainjector",
            "app.kubernetes.io/instance": "cert-manager",
            "app.kubernetes.io/name": "cainjector",
            "app.kubernetes.io/version": "v1.11.0"
          }
        },
        "spec": {
          "containers": [
            {
              "name": "cert-manager-cainjector",
              "image": "quay.io/jetstack/cert-manager-cainjector:v1.11.0",
              "args": [
                "--v=2",
                "--leader-election-namespace=kube-system"
              ],
              "env": [
                {
                  "name": "POD_NAMESPACE",
                  "valueFrom": {
                    "fieldRef": {
                      "apiVersion": "v1",
                      "fieldPath": "metadata.namespace"
                    }
                  }
                }
              ],
              "resources": {},
              "terminationMessagePath": "/dev/termination-log",
              "terminationMessagePolicy": "File",
              "imagePullPolicy": "IfNotPresent",
              "securityContext": {
                "capabilities": {
                  "drop": [
                    "ALL"
                  ]
                },
                "allowPrivilegeEscalation": false
              }
            }
          ],
          "restartPolicy": "Always",
          "terminationGracePeriodSeconds": 30,
          "dnsPolicy": "ClusterFirst",
          "nodeSelector": {
            "kubernetes.io/os": "linux"
          },
          "serviceAccountName": "cert-manager-cainjector",
          "serviceAccount": "cert-manager-cainjector",
          "securityContext": {
            "runAsNonRoot": true,
            "seccompProfile": {
              "type": "RuntimeDefault"
            }
          },
          "schedulerName": "default-scheduler"
        }
      },
      "strategy": {
        "type": "RollingUpdate",
        "rollingUpdate": {
          "maxUnavailable": "25%",
          "maxSurge": "25%"
        }
      },
      "revisionHistoryLimit": 10,
      "progressDeadlineSeconds": 600
    },
    "status": {
      "observedGeneration": 1,
      "replicas": 1,
      "updatedReplicas": 1,
      "readyReplicas": 1,
      "availableReplicas": 1,
      "conditions": [
        {
          "type": "Progressing",
          "status": "True",
          "lastUpdateTime": "2025-02-04T09:47:35Z",
          "lastTransitionTime": "2025-02-04T09:47:33Z",
          "reason": "NewReplicaSetAvailable",
          "message": "ReplicaSet 'cert-manager-cainjector-56ccdfdd58' has successfully progressed."
        },
        {
          "type": "Available",
          "status": "True",
          "lastUpdateTime": "2025-03-27T14:05:42Z",
          "lastTransitionTime": "2025-03-27T14:05:42Z",
          "reason": "MinimumReplicasAvailable",
          "message": "Deployment has minimum availability."
        }
      ]
    }
  }]"""


sample_services_tool_response = """[
  {
    "metadata": {
      "name": "cert-manager",
      "namespace": "cert-manager",
      "uid": "32742220-234d-43bb-9625-7f913a7c61d0",
      "resourceVersion": "147332462",
      "creationTimestamp": "2025-02-04T09:47:33Z",
      "labels": {
        "app": "cert-manager",
        "app.kubernetes.io/component": "controller",
        "app.kubernetes.io/instance": "cert-manager",
        "app.kubernetes.io/name": "cert-manager",
        "app.kubernetes.io/version": "v1.11.0"
      },
      "managedFields": [
        {
          "manager": "kyma",
          "operation": "Apply",
          "apiVersion": "v1",
          "time": "2025-02-04T09:47:33Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:labels": {
                "f:app": {},
                "f:app.kubernetes.io/component": {},
                "f:app.kubernetes.io/instance": {},
                "f:app.kubernetes.io/name": {},
                "f:app.kubernetes.io/version": {}
              }
            },
            "f:spec": {
              "f:ports": {
                "k:{'port':9402,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {},
                  "f:targetPort": {}
                }
              },
              "f:selector": {},
              "f:type": {}
            }
          }
        }
      ]
    },
    "spec": {
      "ports": [
        {
          "name": "tcp-prometheus-servicemonitor",
          "protocol": "TCP",
          "port": 9402,
          "targetPort": 9402
        }
      ],
      "selector": {
        "app.kubernetes.io/component": "controller",
        "app.kubernetes.io/instance": "cert-manager",
        "app.kubernetes.io/name": "cert-manager"
      },
      "clusterIP": "100.65.79.162",
      "clusterIPs": [
        "100.65.79.162"
      ],
      "type": "ClusterIP",
      "sessionAffinity": "None",
      "ipFamilies": [
        "IPv4"
      ],
      "ipFamilyPolicy": "SingleStack",
      "internalTrafficPolicy": "Cluster"
    },
    "status": {
      "loadBalancer": {}
    }
  },
  {
    "metadata": {
      "name": "cert-manager-webhook",
      "namespace": "cert-manager",
      "uid": "15b205e7-a4d7-4a21-b67d-8e43d6c93623",
      "resourceVersion": "147332467",
      "creationTimestamp": "2025-02-04T09:47:33Z",
      "labels": {
        "app": "webhook",
        "app.kubernetes.io/component": "webhook",
        "app.kubernetes.io/instance": "cert-manager",
        "app.kubernetes.io/name": "webhook",
        "app.kubernetes.io/version": "v1.11.0"
      },
      "managedFields": [
        {
          "manager": "kyma",
          "operation": "Apply",
          "apiVersion": "v1",
          "time": "2025-02-04T09:47:33Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:labels": {
                "f:app": {},
                "f:app.kubernetes.io/component": {},
                "f:app.kubernetes.io/instance": {},
                "f:app.kubernetes.io/name": {},
                "f:app.kubernetes.io/version": {}
              }
            },
            "f:spec": {
              "f:ports": {
                "k:{'port':443,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {},
                  "f:targetPort": {}
                }
              },
              "f:selector": {},
              "f:type": {}
            }
          }
        }
      ]
    },
    "spec": {
      "ports": [
        {
          "name": "https",
          "protocol": "TCP",
          "port": 443,
          "targetPort": "https"
        }
      ],
      "selector": {
        "app.kubernetes.io/component": "webhook",
        "app.kubernetes.io/instance": "cert-manager",
        "app.kubernetes.io/name": "webhook"
      },
      "clusterIP": "100.65.222.235",
      "clusterIPs": [
        "100.65.222.235"
      ],
      "type": "ClusterIP",
      "sessionAffinity": "None",
      "ipFamilies": [
        "IPv4"
      ],
      "ipFamilyPolicy": "SingleStack",
      "internalTrafficPolicy": "Cluster"
    },
    "status": {
      "loadBalancer": {}
    }
  },
  {
    "metadata": {
      "name": "kubernetes",
      "namespace": "default",
      "uid": "019c5596-e3d9-461b-9be6-8c956ea74d86",
      "resourceVersion": "193",
      "creationTimestamp": "2024-08-02T11:47:21Z",
      "labels": {
        "component": "apiserver",
        "provider": "kubernetes"
      },
      "managedFields": [
        {
          "manager": "kube-apiserver",
          "operation": "Update",
          "apiVersion": "v1",
          "time": "2024-08-02T11:47:21Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:labels": {
                ".": {},
                "f:component": {},
                "f:provider": {}
              }
            },
            "f:spec": {
              "f:clusterIP": {},
              "f:internalTrafficPolicy": {},
              "f:ipFamilyPolicy": {},
              "f:ports": {
                ".": {},
                "k:{'port':443,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {},
                  "f:targetPort": {}
                }
              },
              "f:sessionAffinity": {},
              "f:type": {}
            }
          }
        }
      ]
    },
    "spec": {
      "ports": [
        {
          "name": "https",
          "protocol": "TCP",
          "port": 443,
          "targetPort": 443
        }
      ],
      "clusterIP": "100.64.0.1",
      "clusterIPs": [
        "100.64.0.1"
      ],
      "type": "ClusterIP",
      "sessionAffinity": "None",
      "ipFamilies": [
        "IPv4"
      ],
      "ipFamilyPolicy": "SingleStack",
      "internalTrafficPolicy": "Cluster"
    },
    "status": {
      "loadBalancer": {}
    }
  },
  {
    "metadata": {
      "name": "istio-ingressgateway",
      "namespace": "istio-system",
      "uid": "46cfa8ca-2ffa-4b27-b140-b1abe1ae362a",
      "resourceVersion": "147333283",
      "creationTimestamp": "2025-02-04T09:48:30Z",
      "labels": {
        "app": "istio-ingressgateway",
        "app.kubernetes.io/instance": "istio",
        "app.kubernetes.io/managed-by": "Helm",
        "app.kubernetes.io/name": "istio-ingressgateway",
        "app.kubernetes.io/part-of": "istio",
        "app.kubernetes.io/version": "1.0.0",
        "helm.sh/chart": "istio-ingress-1.0.0",
        "install.operator.istio.io/owning-resource": "default-operator",
        "install.operator.istio.io/owning-resource-namespace": "istio-system",
        "istio": "ingressgateway",
        "istio.io/rev": "default",
        "operator.istio.io/component": "IngressGateways",
        "operator.istio.io/managed": "Reconcile",
        "operator.istio.io/version": "unknown",
        "release": "istio"
      },
      "annotations": {
        "istios.operator.kyma-project.io/managed-by-disclaimer": "DO NOT EDIT - This resource is managed by Kyma.\nAny modifications are discarded and the resource is reverted to the original state.\n",
        "service.beta.kubernetes.io/aws-load-balancer-connection-idle-timeout": "4000",
        "service.beta.kubernetes.io/aws-load-balancer-proxy-protocol": "*"
      },
      "finalizers": [
        "service.kubernetes.io/load-balancer-cleanup"
      ],
      "managedFields": [
        {
          "manager": "istio-operator",
          "operation": "Apply",
          "apiVersion": "v1",
          "time": "2025-02-04T09:48:29Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:annotations": {
                "f:istios.operator.kyma-project.io/managed-by-disclaimer": {},
                "f:service.beta.kubernetes.io/aws-load-balancer-connection-idle-timeout": {},
                "f:service.beta.kubernetes.io/aws-load-balancer-proxy-protocol": {}
              },
              "f:labels": {
                "f:app": {},
                "f:app.kubernetes.io/instance": {},
                "f:app.kubernetes.io/managed-by": {},
                "f:app.kubernetes.io/name": {},
                "f:app.kubernetes.io/part-of": {},
                "f:app.kubernetes.io/version": {},
                "f:helm.sh/chart": {},
                "f:install.operator.istio.io/owning-resource": {},
                "f:install.operator.istio.io/owning-resource-namespace": {},
                "f:istio": {},
                "f:istio.io/rev": {},
                "f:operator.istio.io/component": {},
                "f:operator.istio.io/managed": {},
                "f:operator.istio.io/version": {},
                "f:release": {}
              }
            },
            "f:spec": {
              "f:ports": {
                "k:{'port':80,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {},
                  "f:targetPort": {}
                },
                "k:{'port':443,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {},
                  "f:targetPort": {}
                },
                "k:{'port':15021,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {},
                  "f:targetPort": {}
                }
              },
              "f:selector": {},
              "f:type": {}
            }
          }
        },
        {
          "manager": "aws-cloud-controller-manager",
          "operation": "Update",
          "apiVersion": "v1",
          "time": "2025-02-04T09:48:32Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:finalizers": {
                ".": {},
                "v:'service.kubernetes.io/load-balancer-cleanup'": {}
              }
            },
            "f:status": {
              "f:loadBalancer": {
                "f:ingress": {}
              }
            }
          },
          "subresource": "status"
        }
      ]
    },
    "spec": {
      "ports": [
        {
          "name": "status-port",
          "protocol": "TCP",
          "port": 15021,
          "targetPort": 15021,
          "nodePort": 30840
        },
        {
          "name": "http2",
          "protocol": "TCP",
          "port": 80,
          "targetPort": 8080,
          "nodePort": 31799
        },
        {
          "name": "https",
          "protocol": "TCP",
          "port": 443,
          "targetPort": 8443,
          "nodePort": 30179
        }
      ],
      "selector": {
        "app": "istio-ingressgateway",
        "istio": "ingressgateway"
      },
      "clusterIP": "100.64.166.123",
      "clusterIPs": [
        "100.64.166.123"
      ],
      "type": "LoadBalancer",
      "sessionAffinity": "None",
      "externalTrafficPolicy": "Cluster",
      "ipFamilies": [
        "IPv4"
      ],
      "ipFamilyPolicy": "SingleStack",
      "allocateLoadBalancerNodePorts": true,
      "internalTrafficPolicy": "Cluster"
    },
    "status": {
      "loadBalancer": {
        "ingress": [
          {
            "hostname": "a46cfa8ca2ffa4b27b140b1abe1ae362-1188520584.eu-west-1.elb.amazonaws.com"
          }
        ]
      }
    }
  },
  {
    "metadata": {
      "name": "istiod",
      "namespace": "istio-system",
      "uid": "c145f4e9-b187-4559-8faf-441a313f9da9",
      "resourceVersion": "147333034",
      "creationTimestamp": "2025-02-04T09:48:19Z",
      "labels": {
        "app": "istiod",
        "app.kubernetes.io/instance": "istio",
        "app.kubernetes.io/managed-by": "Helm",
        "app.kubernetes.io/name": "istiod",
        "app.kubernetes.io/part-of": "istio",
        "app.kubernetes.io/version": "1.0.0",
        "helm.sh/chart": "istiod-1.0.0",
        "install.operator.istio.io/owning-resource": "default-operator",
        "install.operator.istio.io/owning-resource-namespace": "istio-system",
        "istio": "pilot",
        "istio.io/rev": "default",
        "operator.istio.io/component": "Pilot",
        "operator.istio.io/managed": "Reconcile",
        "operator.istio.io/version": "unknown",
        "release": "istio"
      },
      "annotations": {
        "istios.operator.kyma-project.io/managed-by-disclaimer": "DO NOT EDIT - This resource is managed by Kyma.\nAny modifications are discarded and the resource is reverted to the original state.\n",
        "prometheus.io/port": "15014",
        "prometheus.io/scrape": "true"
      },
      "managedFields": [
        {
          "manager": "istio-operator",
          "operation": "Apply",
          "apiVersion": "v1",
          "time": "2025-02-04T09:48:19Z",
          "fieldsType": "FieldsV1",
          "fieldsV1": {
            "f:metadata": {
              "f:annotations": {
                "f:istios.operator.kyma-project.io/managed-by-disclaimer": {},
                "f:prometheus.io/port": {},
                "f:prometheus.io/scrape": {}
              },
              "f:labels": {
                "f:app": {},
                "f:app.kubernetes.io/instance": {},
                "f:app.kubernetes.io/managed-by": {},
                "f:app.kubernetes.io/name": {},
                "f:app.kubernetes.io/part-of": {},
                "f:app.kubernetes.io/version": {},
                "f:helm.sh/chart": {},
                "f:install.operator.istio.io/owning-resource": {},
                "f:install.operator.istio.io/owning-resource-namespace": {},
                "f:istio": {},
                "f:istio.io/rev": {},
                "f:operator.istio.io/component": {},
                "f:operator.istio.io/managed": {},
                "f:operator.istio.io/version": {},
                "f:release": {}
              }
            },
            "f:spec": {
              "f:ports": {
                "k:{'port':443,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {},
                  "f:targetPort": {}
                },
                "k:{'port':15010,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {}
                },
                "k:{'port':15012,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {}
                },
                "k:{'port':15014,'protocol':'TCP'}": {
                  ".": {},
                  "f:name": {},
                  "f:port": {},
                  "f:protocol": {}
                }
              },
              "f:selector": {}
            }
          }
        }
      ]
    },
    "spec": {
      "ports": [
        {
          "name": "grpc-xds",
          "protocol": "TCP",
          "port": 15010,
          "targetPort": 15010
        },
        {
          "name": "https-dns",
          "protocol": "TCP",
          "port": 15012,
          "targetPort": 15012
        },
        {
          "name": "https-webhook",
          "protocol": "TCP",
          "port": 443,
          "targetPort": 15017
        },
        {
          "name": "http-monitoring",
          "protocol": "TCP",
          "port": 15014,
          "targetPort": 15014
        }
      ],
      "selector": {
        "app": "istiod",
        "istio": "pilot"
      },
      "clusterIP": "100.69.175.204",
      "clusterIPs": [
        "100.69.175.204"
      ],
      "type": "ClusterIP",
      "sessionAffinity": "None",
      "ipFamilies": [
        "IPv4"
      ],
      "ipFamilyPolicy": "SingleStack",
      "internalTrafficPolicy": "Cluster"
    },
    "status": {
      "loadBalancer": {}
    }
  }]
"""
