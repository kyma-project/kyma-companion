# Serverless Configuration

## Overview

The Serverless module has its own operator (Serverless operator). It watches the Serverless custom resource (CR) and reconfigures (reconciles) the Serverless workloads.

The Serverless CR becomes an API to configure the Serverless module. You can use it to:
 - enable or disable the internal Docker registry
 - configure the external Docker registry 
 - override endpoint for traces collected by the Serverless Functions
 - override endpoint for eventing
 - override the target CPU utilization percentage
 - override the Function requeue duration
 - override the Function build executor arguments
 - override the Function build max simultaneous jobs
 - override the healthz liveness timeout
 - override the Function request body limit 
 - override the Function timeout
 - override the default build Job preset
 - override the default runtime Pod preset

The default configuration of the Serverless Module is following:

   ```yaml
   apiVersion: operator.kyma-project.io/v1alpha1
   kind: Serverless
   metadata:
     name: serverless-sample
   spec:
     dockerRegistry:
       enableInternal: true
   ```

## Configure Docker Registry

By default, Serverless uses PersistentVolume (PV) as the internal registry to store Docker images for Functions. The default storage size of a single volume is 20 GB. This internal registry is suitable for local development.

If you use Serverless for production purposes, it is recommended that you use an external registry, such as Docker Hub, Artifact Registry, or Azure Container Registry (ACR).

Follow these steps to use the external Docker registry in Serverless: 

1. Create a Secret in the `kyma-system` namespace with the required data (`username`, `password`, `serverAddress`, and `registryAddress`):

   ```bash
   kubectl create secret generic my-registry-config \
       --namespace kyma-system \
       --from-literal=username={USERNAME} \
       --from-literal=password={PASSWORD} \
       --from-literal=serverAddress={SERVER_URL} \
       --from-literal=registryAddress={REGISTRY_URL}
   ```

> [!TIP]
> In case of DockerHub, usually the Docker registry address is the same as the account name.

Examples:

<!-- tabs:start -->

### **Docker Hub**

   ```bash
   kubectl create secret generic my-registry-config \
      --namespace kyma-system \
      --from-literal=username={USERNAME} \
      --from-literal=password={PASSWORD} \
      --from-literal=serverAddress=https://index.docker.io/v1/ \
      --from-literal=registryAddress={USERNAME}
   ```

### **Artifact Registry**

To learn how to set up authentication for Docker with Artifact Registry, visit the [Artifact Registry documentation](https://cloud.google.com/artifact-registry/docs/docker/authentication#json-key).
   ```bash
   kubectl create secret generic my-registry-config \
       --namespace kyma-system \
       --from-literal=username=_json_key \
       --from-literal=password={GCR_KEY_JSON} \
       --from-literal=serverAddress=gcr.io \
       --from-literal=registryAddress=gcr.io/{YOUR_GCR_PROJECT}
   ```

### **ACR**

To learn how to authenticate with ACR, visit the [ACR documentation](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-authentication?tabs=azure-cli#az-acr-login-with---expose-token).

   ```bash
   kubectl create secret generic my-registry-config \
       --namespace kyma-system \
       --from-literal=username=00000000-0000-0000-0000-000000000000 \
       --from-literal=password={ACR_TOKEN} \
       --from-literal=serverAddress={AZ_REGISTRY_NAME}.azurecr.io \
       --from-literal=registryAddress={AZ_REGISTRY_NAME}.azurecr.io
   ```

<!-- tabs:end -->

2. Reference the Secret in the Serverless CR:

   ```yaml
   spec:
     dockerRegistry:
       secretName: my-registry-config 
   ```
The URL of the currently used Docker registry is visible in the Serverless CR status.


## Configure Trace Endpoint

By default, the Serverless operator checks if there is a trace endpoint available. If available, the detected trace endpoint is used as the trace collector URL in Functions.
If no trace endpoint is detected, Functions are configured with no trace collector endpoint.
You can configure a custom trace endpoint so that Function traces are sent to any tracing backend you choose.
The currently used trace endpoint is visible in the Serverless CR status.

   ```yaml
   spec:
     tracing:
       endpoint: http://jaeger-collector.observability.svc.cluster.local:4318/v1/traces
   ```

## Configure Eventing Endpoint

You can configure a custom eventing endpoint, so when you use SDK for sending events from your Functions, it is used to publish events.
The currently used trace endpoint is visible in the Serverless CR status.
By default `http://eventing-publisher-proxy.kyma-system.svc.cluster.local/publish` is used.

   ```yaml
   spec:
     eventing:
       endpoint: http://eventing-publisher-proxy.kyma-system.svc.cluster.local/publish
   ```

## Configure Target CPU Utilization Percentage

You can set a custom target threshold for CPU utilization. The default value is set to `50%`.

```yaml
   spec:
      targetCPUUtilizationPercentage: 50
```

## Configure the Function Requeue Duration

By default, the Function associated with the default configuration will be requeued every 5 minutes.  

```yaml
   spec:
      functionRequeueDuration: 5m
```

## Configure the Function Build Executor Arguments

Use this label to choose the [arguments](https://github.com/GoogleContainerTools/kaniko?tab=readme-ov-file#additional-flags) passed to the Function build executor, for example: 
- `--insecure` - executor operates in an insecure mode
- `--skip-tls-verify` - executor skips the TLS certificate verification
- `--skip-unused-stages` - executor skips any stages that aren't used for the current execution
- `--log-format=text` - executor uses logs in a given format
- `--cache=true` - enables caching for the executor
- `--compressed-caching=false` - Prevents tar compression for cached layers. This will increase the runtime of the build, but decrease the memory usage especially for large builds.
- `--use-new-run` - Improves performance by avoiding the full filesystem snapshots.

```yaml
   spec:
      functionBuildExecutorArgs: "--insecure,--skip-tls-verify,--skip-unused-stages,--log-format=text,--cache=true,--use-new-run,--compressed-caching=false"
```

## Configure the Function Build Max Simultaneous Jobs

You can set a custom maximum number of simultaneous jobs which can run at the same time. The default value is set to `5`.

```yaml
   spec:
      functionBuildMaxSimultaneousJobs: 5
```

## Configure the healthz Liveness Timeout

By default, the Function is considered unhealthy if the liveness health check endpoint does not respond within 10 seconds.

```yaml
   spec:
      healthzLivenessTimeout: "10s"
```

## Configure the Function Request Body Limit

Use this field to configure the maximum size limit for the request body of a Function. The default value is set to `1` megabyte.

```yaml
   spec:
      functionRequestBodyLimitMb: 1
```

## Configure the Function Timeout

By default, the maximum execution time limit for a Function is set to `180` seconds.

```yaml
   spec:
      functionTimeoutSec: 180
```

## Configure the Default Build Job Preset

You can configure the default build Job preset to be used. 

```yaml
   spec:
      defaultBuildJobPreset: "normal"
```

## Configure the Default Runtime Pod Preset

You can configure the default runtime Pod preset to be used.

```yaml
   spec:
      defaultRuntimePodPreset: "M"
```
