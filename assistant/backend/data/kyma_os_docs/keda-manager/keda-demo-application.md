## Keda Demo Application

This demo application shows how to scale the Kubernetes workloads using Keda API based on a simple CPU consumption case.

See the Keda documentation:
 - [API of Scaled Object Custom Resource](https://keda.sh/docs/latest/concepts/scaling-deployments/#scaledobject-spec)
 - [Available scalers](https://keda.sh/docs/latest/scalers/)

It consists of:
 - order-service deployment (serving as a scale target)
 - busybox deployment (generating trafic)
 - scaled object using a simple CPU-based trigger

### Deploy Demo Application

```bash
kubectl apply -f examples/keda-cpu-scaler-demo.yml
```

### Verify Demo Application

You should see that scaled object is created and has a status READY:

```bash
kunectl get scaledobjects.keda.sh -n keda-demo
NAME                        SCALETARGETKIND      SCALETARGETNAME   MIN   MAX   TRIGGERS   AUTHENTICATION   READY   ACTIVE   FALLBACK   AGE
orders-service-cpu-scaler   apps/v1.Deployment   orders-service    1     10    cpu                         True    True     Unknown    8m3s
```

You should also see that after a while, Keda has engaged the Kubernetes HorizontalPodAutoscaler, which controls the number of replicas of the target deployment.

```bash
kubectl get hpa -n keda-demo
NAMESPACE   NAME                                 REFERENCE                   TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
keda-demo   keda-hpa-orders-service-cpu-scaler   Deployment/orders-service   80%/30%   1         10        4          31s
```
