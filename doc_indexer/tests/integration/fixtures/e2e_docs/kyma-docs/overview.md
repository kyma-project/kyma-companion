# Kyma Overview

Kyma is an opinionated set of Kubernetes-based modular building blocks that includes the necessary capabilities to develop and run enterprise-grade cloud-native applications.
It is the open path to the SAP ecosystem supporting business scenarios end-to-end, and by giving developers a set of tools to use in their projects.

## Key Features

Kyma provides a set of features that help you build and run cloud-native applications.
These features are grouped into modules that you can enable or disable depending on your needs.
Each module is a self-contained unit that can be deployed and managed independently.

## Architecture

The Kyma architecture is based on Kubernetes and leverages its capabilities to provide a scalable and resilient platform.
It uses a microservices approach where each component is responsible for a specific set of tasks.
The components communicate with each other using well-defined APIs and protocols.

### Control Plane

The control plane is responsible for managing the lifecycle of the Kyma components.
It handles the installation, configuration, and upgrade of the modules.
The control plane also provides a central point of management for the entire Kyma installation.

### Data Plane

The data plane is responsible for processing the actual workloads.
It runs the application components and handles the data flow between them.
The data plane is designed to be highly available and fault-tolerant.
