---
title: Deploy a Kyma Application with Redis
description: Learn how to deploy a sample application that uses Redis as a cache layer in a Kyma environment.
time: 30
auto_validation: true
tags: [ tutorial>beginner, products>sap-btp-kyma-runtime ]
primary_tag: products>sap-btp-kyma-runtime
---

# Deploy a Kyma Application with Redis

## Prerequisites

- You have a Kyma environment provisioned on SAP BTP.
- You have the Kyma CLI installed. See [Install Kyma CLI](../cp-kyma-download-cli/cp-kyma-download-cli.md).
- `kubectl` is configured against your Kyma cluster.

## Overview

In this tutorial, you deploy a simple Node.js application backed by a Redis cache into your Kyma runtime. You use a Kyma Function and a Redis StatefulSet, connected via a Kubernetes Service.

## Step 1 -- Create a Namespace

Create a dedicated namespace for the tutorial:

```bash
kubectl create namespace redis-demo
kubectl label namespace redis-demo istio-injection=enabled
```

## Step 2 -- Deploy Redis

Apply the following manifest to deploy a single-node Redis instance:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: redis-demo
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "100m"
```

Apply the manifest:

```bash
kubectl apply -f redis.yaml
```

## Step 3 -- Expose Redis as a Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: redis-demo
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
```

```bash
kubectl apply -f redis-service.yaml
```

## Step 4 -- Deploy the Kyma Function

Create a Kyma Function that reads and writes to Redis:

```yaml
apiVersion: serverless.kyma-project.io/v1alpha2
kind: Function
metadata:
  name: redis-counter
  namespace: redis-demo
spec:
  runtime: nodejs20
  source:
    inline:
      source: |
        const redis = require('redis');
        const client = redis.createClient({ url: 'redis://redis:6379' });

        module.exports = { main: async function(event, context) {
          await client.connect();
          const count = await client.incr('visits');
          await client.disconnect();
          return { visits: count };
        }};
      dependencies: |
        {
          "name": "redis-counter",
          "version": "1.0.0",
          "dependencies": {
            "redis": "^4.0.0"
          }
        }
```

```bash
kubectl apply -f function.yaml
```

## Step 5 -- Expose the Function

Create an `APIRule` to expose the Function externally:

```yaml
apiVersion: gateway.kyma-project.io/v2
kind: APIRule
metadata:
  name: redis-counter
  namespace: redis-demo
spec:
  hosts:
    - redis-counter.<your-cluster-domain>
  gateway: kyma-system/kyma-gateway
  rules:
    - path: /.*
      methods: [GET]
      noAuth: true
      service:
        name: redis-counter
        port: 80
```

Replace `<your-cluster-domain>` with your cluster's domain, then apply:

```bash
kubectl apply -f apirule.yaml
```

## Step 6 -- Test the Deployment

Call the exposed endpoint to verify the counter increments on each request:

```bash
curl https://redis-counter.<your-cluster-domain>
```

Expected response:

```json
{"visits": 1}
```

Call it again and confirm the counter increments:

```json
{"visits": 2}
```

## Clean Up

Remove all resources when you are done:

```bash
kubectl delete namespace redis-demo
```

## Related Tutorials

- [Create a Kyma Function via CLI](../cp-kyma-create-function-cli/cp-kyma-create-function-cli.md)
- [Expose a Service with APIRule](../cp-kyma-gateway-api/cp-kyma-gateway-api.md)
