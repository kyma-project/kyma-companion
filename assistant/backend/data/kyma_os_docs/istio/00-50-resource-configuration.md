# Default Resources and Autoscaling Configuration for Kyma Istio Operator

Kyma Istio Operator provides baseline values for the Istio installation. Those values can be overridden with configuration in the Istio custom resource (CR).

## Cluster-Based Default Configuration

Istio Controller installs Istio with a configuration that depends in the cluster capabilities. If your cluster has less than 5 total virtual CPU cores or its total memory capacity is less than 10 Gigabytes, the default setup for resources and autoscaling is lighter. If your cluster exceeds both of these thresholds, Istio is installed with the higher resource configuration.

### Default Resource Configuration for Larger Clusters

| Component       |          | CPU   | Memory |
|-----------------|----------|-------|--------|
| Proxy           | Limits   | 1000m | 1024Mi |
| Proxy           | Requests | 10m   | 192Mi  |
| Ingress Gateway | Limits   | 2000m | 1024Mi |
| Ingress Gateway | Requests | 100m  | 128Mi  |
| Pilot           | Limits   | 4000m | 2Gi    |
| Pilot           | Requests | 100m  | 512Mi  |
| CNI             | Limits   | 500m  | 1024Mi |
| CNI             | Requests | 100m  | 512Mi  |

### Default Autoscaling Configuration for Larger Clusters

| Component       | Min replicas | Max replicas |
|-----------------|--------------|--------------|
| Pilot           | 2            | 5            |
| Ingress Gateway | 3            | 10           |

### Default Resource Configuration for Smaller Clusters

| Component       |          | CPU   | Memory |
|-----------------|----------|-------|--------|
| Proxy           | Limits   | 250m  | 254Mi  |
| Proxy           | Requests | 10m   | 32Mi   |
| Ingress Gateway | Limits   | 1000m | 1024Mi |
| Ingress Gateway | Requests | 10m   | 32Mi   |
| Pilot           | Limits   | 1000m | 1024Mi |
| Pilot           | Requests | 50m   | 128Mi  |
| CNI             | Limits   | 250m  | 384Mi  |
| CNI             | Requests | 10m   | 128Mi  |

### Default Autoscaling Configuration for Smaller Clusters

| Component       | Min replicas | Max replicas |
|-----------------|--------------|--------------|
| Pilot           | 1            | 1            |
| Ingress Gateway | 1            | 3            |

### CNI Autoscaling

The CNI component is provided as a DaemonSet, meaning that one replica is present on every node of the target cluster.
