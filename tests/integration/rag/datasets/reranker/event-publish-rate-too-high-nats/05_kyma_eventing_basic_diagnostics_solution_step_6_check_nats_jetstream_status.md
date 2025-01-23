# Kyma Eventing - Basic Diagnostics - Solution - Step 6: Check NATS JetStream Status
1. Check the health of NATS Pods. Run the command:
```bash
kubectl -n kyma-system get pods -l nats_cluster=eventing-nats
```
2. Check if the stream and consumers exist in NATS JetStream by following the [JetStream troubleshooting guide](evnt-02-jetstream-troubleshooting.md).
If you can't find a solution, don't hesitate to create a [GitHub](https://github.com/kyma-project/kyma/issues) issue or reach out to our [Slack channel](https://kyma-community.slack.com/) to get direct support from the community.