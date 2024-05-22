# Issues with Istio Sidecar Injection

## Symptom

A Pod doesn't have a sidecar but you did not disable sidecar injection on purpose.

## Cause

By default, Kyma Istio Operator has sidecar injection disabled - there is no automatic sidecar injection into any Pod in a cluster.

## Remedy

To check if your Pod and its namespace have Istio sidecar injected, read [Check if you have Istio sidecar proxy injection enabled](../operation-guides/02-10-check-if-sidecar-injection-is-enabled.md). Learn how to [enable Istio sidecar proxy injection](../operation-guides/02-20-enable-sidecar-injection.md).