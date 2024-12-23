# Kyma Eventing - Basic Diagnostics - Solution - Step 4: Check the Eventing Manager Logs
1. Check the logs from the Eventing Manager Pod for any errors and to verify that the event is dispatched.
To fetch these logs, run this command:
```bash
kubectl -n kyma-system logs -l app.kubernetes.io/instance=eventing-manager,app.kubernetes.io/name=eventing-manager
```
2. Check for any error messages in the logs. If the event dispatch log `"message":"event dispatched"` is not present for NATS backend, the issue could be one of the following:
- The subscriber (the sink) is not reachable or the subscriber cannot process the event. Check the logs of the subscriber instance.
- The event was published in a wrong format.
- Eventing Manager cannot connect to NATS Server.