# Kyma Eventing - Basic Diagnostics - Solution - Step 1: Check the Status of the Eventing Custom Resource
1. Check the Eventing CR. Is the **State** field `Ready`?
```bash
kubectl -n kyma-system get eventings.operator.kyma-project.io
```
2. If **State** is not `Ready`, check the exact reason of the error in the status of the CR by running the command:
```bash
kubectl -n kyma-system get eventings.operator.kyma-project.io eventing -o yaml
```
3. If the **State** is `Ready`, the Eventing CR is not an issue. Follow the next steps to find the source of the problem.