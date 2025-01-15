# Integrate with SAP Cloud Logging - Set Up Kyma Dashboard Integration
For easier access from the Kyma dashboard, add links to the navigation under **SAP Cloud Logging**, and add deep links to the **Pod**, **Deployment**, and **Namespace** views.
1. Apply the ConfigMap:
```bash
kubectl apply -f https://raw.githubusercontent.com/kyma-project/telemetry-manager/main/docs/user/integration/sap-cloud-logging/kyma-dashboard-configmap.yaml
```
2. If your Secret has a different name or namespace, then download the file first and adjust the namespace and name accordingly in the 'dataSources' section of the file.