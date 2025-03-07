RETRIEVAL_CONTEXT = """
# BTP Manager  
## Overview  
BTP Manager is an operator for the [SAP BTP service operator](https://github.com/SAP/sap-btp-service-operator) based on the [Kubebuilder](https://github.com/kubernetes-sigs/kubebuilder) framework. It extends Kubernetes API by providing [BtpOperator CustomResourceDefinition](/config/crd/bases/operator.kyma-project.io_btpoperators.yaml) (CRD), which allows you to manage the SAP BTP service operator resource through custom resource (CR). BTP Manager and the SAP BTP service operator constitute the SAP BTP Operator module.  
## Installation  
To enable the SAP BTP Operator module from the latest release, you must install BTP Manager. For installation instructions, see [Install the SAP BTP Operator module](./docs/user/03-05-install-module.md).  
## Usage  
Use SAP BTP Operator to create SAP BTP services in your Kyma cluster. To find out how to do it, see the tutorial [Create an SAP BTP Service Instance in Your Kyma Cluster](./docs/user/tutorials/04-40-create-service-in-cluster.md).  
## Uninstallation  
To uninstall SAP BTP Operator, run the following commands:
```sh
kubectl delete -f https://github.com/kyma-project/btp-manager/releases/latest/download/btp-operator-default-cr.yaml
kubectl delete -f https://github.com/kyma-project/btp-manager/releases/latest/download/btp-manager.yaml
```  
## Read More  
If you want to provide new features for BTP Manager, visit the [`contributor`](./docs/contributor) folder. You will find detailed information on BTP Manager's:  
* [configuration](./docs/contributor/01-20-configuration.md)
* [operations](./docs/contributor/02-10-operations.md)
* [release pipeline](./docs/contributor/03-10-release.md)
* [GitHub Actions workflows](./docs/contributor/04-10-workflows.md)
* [unit tests](./docs/contributor/05-10-testing.md)
* [E2E tests](./docs/contributor/05-20-e2e_tests.md)
* [certification management](./docs/contributor/06-10-certs.md)
* [informer's cache](./docs/contributor/07-10-informer-cache.md)
* [metrics](./docs/contributor/08-10-metrics.md)  
In the [`user`](./docs/user) folder, you will find the following documents:
* [SAP BTP Operator Module](./docs/user/README.md)
* [Create the `sap-btp-manager` Secret](./docs/user/03-00-create-btp-manager-secret.md)
* [Install the SAP BTP Operator Module](./docs/user/03-05-install-module.md)
* [Preconfigured Credentials and Access](./docs/user/03-10-preconfigured-secret.md)
* [Working with Multiple Subaccounts](./docs//user/03-20-multitenancy.md)
* [Create a Service Instance with a Custom Secret](./docs/user/03-21-create-service-instance-with-custom-secret.md)
* [Create a Service Instance with a Namespace-Based Secret](./docs/user/03-22-create-service-instance-with-namespace-based-secret.md)
* [Management of the Service Instances and Service Bindings Lifecycle](./docs//user/03-30-management-of-service-instances-and-bindings.md)
* [Service Binding Rotation](./docs//user/03-40-service-binding-rotation.md)
* [Formats of Service Binding Secrets](./docs//user/03-50-formatting-service-binding-secret.md)
* [Resources](./docs/user/resources/README.md)
* [SAP BTP Operator Custom Resource](./docs/user/resources/02-10-sap-btp-operator-cr.md)
* [Service Instance Custom Resource](./docs/user/resources/02-20-service-instance-cr.md)
* [Service Binding Custom Resource](./docs/user/resources/02-30-service-binding-cr.md)
* [Tutorials](./docs/user/tutorials/README.md)
* [Create an SAP BTP Service Instance in Your Kyma Cluster](./docs/user/tutorials/04-40-create-service-in-cluster.md)  
## Contributing
<!--- mandatory section - do not change this! --->  
See the [Contributing](CONTRIBUTING.md) guidelines.  
## Code of Conduct
<!--- mandatory section - do not change this! --->  
See the [Code of Conduct](CODE_OF_CONDUCT.md) document.  
## Licensing
<!--- mandatory section - do not change this! --->  
See the [license](./LICENSE) file.
# SAP BTP Operator Module  
Learn more about the SAP BTP Operator module. Use it to enable Service Management and consume SAP BTP services from your Kyma cluster.  
## What is SAP BTP Operator?  
The SAP BTP Operator module provides Service Management, which allows you to consume [SAP BTP services](https://discovery-center.cloud.sap/protected/index.html#/viewServices) from your Kyma cluster using Kubernetes-native tools.
Within the SAP BTP Operator module, [BTP Manager](https://github.com/kyma-project/btp-manager) installs an open source component: the [SAP BTP service operator](https://github.com/SAP/sap-btp-service-operator/blob/main/README.md).
The SAP BTP service operator enables provisioning and managing service instances and service bindings of SAP BTP services so that your Kubernetes-native applications can access and use the services from your cluster.  
## Features  
The SAP BTP Operator module provides the following features:
* [Credentials and access preconfiguration](03-10-preconfigured-secret.md): Your Secret is provided on Kyma runtime creation.
* [Multitenancy](03-20-multitenancy.md): You can configure multiple subaccounts in a single cluster.
* [Lifecycle management of service instances and service bindings](03-30-management-of-service-instances-and-bindings.md): You can create and delete service instances and service bindings.
* [Service binding rotation](03-40-service-binding-rotation.md): You can enhance security by automatically rotating the credentials associated with your service bindings.
* [Service binding Secret formatting](03-50-formatting-service-binding-secret.md): You can use different attributes in your ServiceBinding resource to generate different formats of your Secret resources.  
## Scope  
By default, the scope of the SAP BTP Operator module is your Kyma runtime, which consumes SAP BTP services from the subaccount in which you created it. You can extend the module's scope by adding more subaccounts and consuming services from them in one cluster. The scope can range from one to multiple subaccounts depending on the number of configured Secrets.  
## Architecture  
The SAP BTP Operator module provides and retrieves the initial credentials that your application needs to use an SAP BTP service.  
![SAP BTP Operator architecture](../assets/module_architecture.drawio.svg)  
SAP BTP Operator can have access to multiple subaccounts within your cluster depending on the number of configured Secrets.  
![Access configuration](../assets/access_configuration.drawio.svg)  
For more information on multitenancy, see [Working with Multiple Subaccounts](03-20-multitenancy.md).  
### SAP BTP, Kyma Runtime  
SAP BTP, Kyma runtime runs on a Kubernetes cluster and wraps the SAP BTP Operator module, API server, and one or more applications. The application or multiple applications are the actual consumers of SAP BTP services.  
### BTP Manager  
BTP Manager is an operator based on the [Kubebuilder](https://github.com/kubernetes-sigs/kubebuilder) framework. It extends the Kubernetes API by providing the [BtpOperator Custom Resource Definition (CRD)](https://github.com/kyma-project/btp-manager/blob/main/config/crd/bases/operator.kyma-project.io_btpoperators.yaml).
BTP Manager performs the following operations:
* Manages the lifecycle of the SAP BTP service operator, including provisioning of the latest version, updating, and deprovisioning
* Configures the SAP BTP service operator  
### SAP BTP Service Operator  
The SAP BTP service operator is an open-source component that connects SAP BTP services to your cluster and manages them using Kubernetes-native tools. It is responsible for communicating with SAP Service Manager. The operator's resources (service instances and service bindings) come from the `services.cloud.sap.com` API group.  
### SAP Service Manager  
[SAP Service Manager](https://help.sap.com/docs/service-manager/sap-service-manager/sap-service-manager?locale=en-US) is the central registry for service brokers and platforms in SAP BTP, which enables you to:
* Consume platform services in any connected runtime environment
* Track the creation and management of service instances
* Share services and service instances between different runtimes  
SAP Service Manager uses [Open Service Broker API](https://www.openservicebrokerapi.org/) (OSB API) to communicate with service brokers.  
### Service Brokers  
Service brokers manage the lifecycle of services. SAP Service Manager interacts with service brokers using OSB API to provision and manage service instances and service bindings.  
## API / Custom Resource Definitions  
The `btpoperators.operator.kyma-project.io` Custom Resource Definition (CRD) describes the kind and the data format that SAP BTP Operator uses to configure resources.  
See the documentation related to the BtpOperator custom resource (CR):
* [SAP BTP Operator](./resources/02-10-sap-btp-operator-cr.md)
* [Service instance](./resources/02-20-service-instance-cr.md)
* [Service binding](./resources/02-30-service-binding-cr.md)  
## Resource Consumption  
To learn more about the resources the SAP BTP Operator module uses, see [Kyma Modules' Sizing](https://help.sap.com/docs/btp/sap-business-technology-platform-internal/kyma-modules-sizing?locale=en-US&state=DRAFT&version=Internal#sap-btp-operator).
[![REUSE status](https://api.reuse.software/badge/github.com/kyma-project/btp-manager)](https://api.reuse.software/info/github.com/kyma-project/btp-manager)
"""

EXPECTED_BTP_MANAGER_RESPONSE = """
The SAP BTP Operator module provides the following features:
 - Credentials and access preconfiguration: Your Secret is provided on Kyma runtime creation.
 - Multitenancy: You can configure multiple subaccounts in a single cluster.
 - Lifecycle management of service instances and service bindings: You can create and delete service instances and service bindings.
 - Service binding rotation: You can enhance security by automatically rotating the credentials associated with your service bindings.
 -Service binding Secret formatting: You can use different attributes in your ServiceBinding resource to generate different formats of your Secret resources.
"""
