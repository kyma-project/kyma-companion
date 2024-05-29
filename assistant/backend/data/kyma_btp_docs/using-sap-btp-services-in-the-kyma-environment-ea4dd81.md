

# Using SAP BTP Services in the Kyma Environment

With the Kyma environment, you can connect SAP BTP services to your cluster and manage them using SAP BTP Service Operator.





## Prerequisites

-   The SAP BTP Operator module is added, see [Add and Delete a Kyma Module](add-and-delete-a-kyma-module-1b548e9.md#loio1b548e9ad4744b978b8b595288b0cb5c). Otherwise, you get the following error message: `resource mapping not found for {...} ensure CRDs are installed first`.

-   For CLI interactions: [kubectl](https://kubernetes.io/docs/tasks/tools/) v1.17 or higher.

-   You know the `serviceOfferingName` and `servicePlanName` for the SAP BTP service you want to connect to the Kyma cluster. You find these values in the Service Marketplace of the SAP BTP cockpit. Click on the service's tile and find *name* and *Plan*, respectively.


> ### Note:  
> You can use [SAP BTP kubectl plugin](https://github.com/SAP/sap-btp-service-operator#sap-btp-kubectl-plugin-experimental) to get the available services in your SAP BTP account by using the access credentials stored in the cluster. However, the plugin is still experimental.





## Creating and Managing Services Using Kyma dashboard

Create and manage Service Instances and Service Bindings using Kyma dashboard.



## Context

Use Kyma dashboard to create and manage your resources.



## Procedure

1.  In the *Namespace* view, go to *Service Management**→Service Instances*.

2.  Create Service Instance using the required service details.

    You see the status `PROVISIONED`.

3.  Go to *Service Management**→Service Bindings* and create Service Binding, choosing your instance name from the dropdown list.

    You see the status `PROVISIONED`.






## Results

You can now use a given service in your Kyma cluster.





## Creating and Managing Services Using kubectl

Create and manage Service Instances and Service Bindings using kubectl.



## Context

Use kubectl to create and manage your resources.





## Procedure

1.  Create a Service Instance:

    ```
    kubectl create -f - <<EOF
    apiVersion: services.cloud.sap.com/v1
    kind: ServiceInstance
    metadata:
      name: {INSTANCE_NAME}
      namespace: {NAMESPACE}
    spec:
      serviceOfferingName: {NAME_FROM_SERVICE_MARKETPLACE}
      servicePlanName: {PLAN_FROM_SERVICE_MARKETPLACE}
      externalName: {INSTANCE_NAME}
    EOF
    ```

2.  To see the output, run:

    ```
    kubectl get serviceinstances.services.cloud.sap.com {INSTANCE_NAME} -o yaml
    ```

    You can see the status ***created*** and the message ***ServiceInstance provisioned successfully***.

3.  Create a Service Binding:

    ```
    kubectl create -f - <<EOF
    apiVersion: services.cloud.sap.com/v1
    kind: ServiceBinding
    metadata:
      name: {BINDING_NAME}
      namespace: {NAMESPACE}
    spec:
      serviceInstanceName: {INSTANCE_NAME}
      externalName: {BINDING_NAME}
      secretName: {BINDING_NAME}
      parameters:
          key1: val1
          key2: val2
    EOF
    ```

4.  To see the output, run:

    ```
    kubectl get servicebindings.services.cloud.sap.com {BINDING_NAME} -o yaml
    ```

    You can see the status ***created*** and the message ***ServiceBinding provisioned successfully***.






## Results

You can now use a given service in your Kyma cluster. To see credentials, run:

```
kubectl get secret {BINDING_NAME} -o yaml
```





## Next Steps

To clean up your resources, run:

```
kubectl delete servicebindings.services.cloud.sap.com {BINDING_NAME}
kubectl delete serviceinstances.services.cloud.sap.com {INSTANCE_NAME}
```

