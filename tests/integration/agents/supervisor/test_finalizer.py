from textwrap import dedent

import pytest
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from integration.agents.test_common_node import create_mock_state


@pytest.mark.parametrize(
    "messages, expected_answer",
    [
        # Finalizer answers based on Kyma agent's response
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="What is Kyma?"),
                AIMessage(
                    name="KymaAgent",
                    content=dedent(
                        """
                        Kyma is an open-source platform designed to extend
                        applications with microservices and serverless functions. It provides a set of tools and
                        components that enable developers to build, deploy, and manage cloud-native applications. Key
                        features of Kyma include: 1. **Kubernetes-based**: Kyma runs on Kubernetes, leveraging its
                        orchestration capabilities for managing containerized applications. 2. **Microservices
                        Architecture**: It supports the development of microservices, allowing for modular application
                        design and easier scaling. 3. **Serverless Functions**: Kyma enables the creation of serverless
                        functions, which can be triggered by events, making it easier to build event-driven applications.
                        4. **Integration Capabilities**: It offers various integration options with external services and
                        APIs, facilitating seamless communication between different systems. 5. **Extensibility**:
                        Developers can extend existing applications with new functionalities without needing to modify
                        the core application code. 6. **Service Management**: Kyma provides tools for managing services,
                        including service discovery, monitoring, and logging. Overall, Kyma is aimed at simplifying the
                        development and management of cloud-native applications, making it easier for organizations to
                        innovate and respond to changing business needs.
                        """
                    ),
                ),
            ],
            dedent(
                """
            Kyma is an open-source platform designed to extend applications with microservices and serverless functions.
            It provides a set of tools and components that enable developers to build, deploy, and manage cloud-native
            applications. Key features of Kyma include:
            1. **Kubernetes-based**: Kyma runs on Kubernetes, leveraging its orchestration capabilities for managing
            containerized applications.
            2. **Microservices Architecture**: It supports the development of microservices, allowing for modular
            application design and easier scaling.
            3. **Serverless Functions**: Kyma enables the creation of serverless functions, which can be triggered by
            events, making it easier to build event-driven applications.
            4. **Integration Capabilities**: It offers various integration options with external services and APIs,
            facilitating seamless communication between different systems.
            5. **Extensibility**: Developers can extend existing applications with new functionalities without needing
            to modify the core application code.
            6. **Service Management**: Kyma provides tools for managing services, including service discovery,
            monitoring, and logging.
            Overall, Kyma is aimed at simplifying the development and management of cloud-native applications, making it
            easier for organizations to innovate and respond to changing business needs.
            """
            ),
        ),
        # Finalizer ignores invalid response from Kyma agent and answers the question itself
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="What is Kyma?"),
                AIMessage(name="KymaAgent", content="It is a color of fish."),
            ],
            dedent(
                """
            Kyma is an open-source platform designed to extend applications with microservices and serverless functions.
            It provides a set of tools and components that enable developers to build, deploy, and manage cloud-native
            applications. Key features of Kyma include:
            1. **Kubernetes-based**: Kyma runs on Kubernetes, leveraging its orchestration capabilities for managing
            containerized applications.
            2. **Microservices Architecture**: It supports the development of microservices, allowing for modular
            application design and easier scaling.
            3. **Serverless Functions**: Kyma enables the creation of serverless functions, which can be triggered by
            events, making it easier to build event-driven applications.
            4. **Integration Capabilities**: It offers various integration options with external services and APIs,
            facilitating seamless communication between different systems.
            5. **Extensibility**: Developers can extend existing applications with new functionalities without needing
            to modify the core application code.
            6. **Service Management**: Kyma provides tools for managing services, including service discovery,
            monitoring, and logging.
            Overall, Kyma is aimed at simplifying the development and management of cloud-native applications, making it
            easier for organizations to innovate and respond to changing business needs.
            """
            ),
        ),
        # Finalizer answers based on K8S agent's response
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="What is k8s?"),
                AIMessage(
                    name="KubernetesAgent",
                    content=dedent(
                        """
                        Kubernetes, often abbreviated as K8s, is an open-source platform designed to automate the deployment,
                        scaling, and management of containerized applications. It provides a framework to run distributed systems
                        resiliently, taking care of scaling and failover for your application, providing deployment patterns, and
                        more. Kubernetes is widely used for managing microservices architectures and is known for its ability to
                        handle complex container orchestration tasks efficiently.
                        """
                    ),
                ),
            ],
            dedent(
                """
            Kubernetes, often abbreviated as K8s, is an open-source platform designed to automate the deployment,
            scaling, and management of containerized applications. It provides a framework to run distributed systems
            resiliently, taking care of scaling and failover for your application, providing deployment patterns, and
            more. Kubernetes is widely used for managing microservices architectures and is known for its ability to
            handle complex container orchestration tasks efficiently.
            """
            ),
        ),
        # Finalizer ignores invalid response from K8S agent and answers the question itself
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="What is k8s?"),
                AIMessage(name="KubernetesAgent", content="The sky is blue."),
            ],
            dedent(
                """
            Kubernetes, often abbreviated as K8s, is an open-source platform designed to automate the deployment,
            scaling, and management of containerized applications. It provides a framework to run distributed systems
            resiliently, taking care of scaling and failover for your application, providing deployment patterns, and
            more. Kubernetes is widely used for managing microservices architectures and is known for its ability to
            handle complex container orchestration tasks efficiently.
            """
            ),
        ),
        # Finalizer ignores the K8S agent's response and answers the question itself
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="What is k8s?"),
                AIMessage(
                    name="KubernetesAgent",
                    content="Sorry, I need more steps to process the request.",
                ),
            ],
            dedent(
                """
                Kubernetes, often abbreviated as K8s, is an open-source platform designed to automate the deployment,
                scaling, and management of containerized applications. It provides a framework to run distributed systems
                resiliently, taking care of scaling and failover for your application, providing deployment patterns, and
                more. Kubernetes is widely used for managing microservices architectures and is known for its ability to
                handle complex container orchestration tasks efficiently.
                """
            ),
        ),
        # Finalizer answers based on K8S and Kyma agents' responses
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(
                    content="what are the types of a k8s service? what is a kyma function?"
                ),
                AIMessage(
                    name="KubernetesAgent",
                    content=dedent(
                        """
                Kubernetes services can be of several types, each serving a different purpose. The main types of
                Kubernetes services are:
                1. **ClusterIP**: Exposes the service on a cluster-internal IP. This type makes the service only
                reachable from within the cluster. It is the default type of service.
                2. **NodePort**: Exposes the service on each Node’s IP at a static port (the NodePort). A ClusterIP
                service, to which the NodePort service routes, is automatically created. You’ll be able to contact the
                NodePort service, from outside the cluster, by requesting `<NodeIP>:<NodePort>`.
                3. **LoadBalancer**: Exposes the service externally using a cloud provider’s load balancer. NodePort and
                ClusterIP services, to which the external load balancer routes, are automatically created.
                4. **ExternalName**: Maps the service to the contents of the `externalName` field (e.g.,
                `foo.bar.example.com`), by returning a CNAME record with its value. No proxying of any kind is set up.
                These types allow Kubernetes to offer different ways to expose applications depending on the use case
                and the environment in which the cluster is running.
                """
                    ),
                ),
                AIMessage(
                    name="KymaAgent",
                    content=dedent(
                        """
                A Kyma function is a lightweight, serverless function that runs in the Kyma environment. It allows you
                to execute custom business logic in response to events or HTTP requests. Functions are typically written
                in JavaScript or TypeScript and can be deployed easily within the Kyma ecosystem.
                Key features of Kyma functions include:
                1. **Event-Driven**: Functions can be triggered by various events, such as HTTP requests, messages from
                a message broker, or other events in the Kyma environment.
                2. **Scalability**: They automatically scale based on demand, allowing you to handle varying loads
                without manual intervention.
                3. **Integration**: Functions can easily integrate with other services and components in the Kyma
                ecosystem, such as APIs, databases, and external services.
                4. **Isolation**: Each function runs in its own isolated environment, ensuring that they do not
                interfere with each other.
                Overall, Kyma functions are a powerful way to extend the capabilities of your applications in a
                cloud-native environment.
                5. **Easy Deployment**: Functions can be deployed using the Kyma console, CLI, or CI/CD pipelines,
                making it straightforward to manage and update them.
                """
                    ),
                ),
            ],
            dedent(
                """
            Kubernetes services can be of several types, each serving a different purpose. The main types of Kubernetes
            services are:
            1. **ClusterIP**: Exposes the service on a cluster-internal IP. This type makes the service only reachable
            from within the cluster. It is the default type of service.
            2. **NodePort**: Exposes the service on each Node’s IP at a static port (the NodePort). A ClusterIP service,
            to which the NodePort service routes, is automatically created. You’ll be able to contact the NodePort
            service, from outside the cluster, by requesting `<NodeIP>:<NodePort>`.
            3. **LoadBalancer**: Exposes the service externally using a cloud provider’s load balancer. NodePort and
            ClusterIP services, to which the external load balancer routes, are automatically created.
            4. **ExternalName**: Maps the service to the contents of the `externalName` field (e.g.,
            `foo.bar.example.com`), by returning a CNAME record with its value. No proxying of any kind is set up.
            These types allow Kubernetes to offer different ways to expose applications depending on the use case and
            the environment in which the cluster is running.
            A Kyma function is a lightweight, serverless function that runs in the Kyma environment. It allows you to
            execute custom business logic in response to events or HTTP requests. Functions are typically written in
            JavaScript or TypeScript and can be deployed easily within the Kyma ecosystem.
            Key features of Kyma functions include:
            1. **Event-Driven**: Functions can be triggered by various events, such as HTTP requests, messages from a
            message broker, or other events in the Kyma environment.
            2. **Scalability**: They automatically scale based on demand, allowing you to handle varying loads without
            manual intervention.
            3. **Integration**: Functions can easily integrate with other services and components in the Kyma ecosystem,
            such as APIs, databases, and external services.
            4. **Isolation**: Each function runs in its own isolated environment, ensuring that they do not interfere
            with each other.
            5. **Easy Deployment**: Functions can be deployed using the Kyma console, CLI, or CI/CD pipelines, making it
            straightforward to manage and update them.
            Overall, Kyma functions are a powerful way to extend the capabilities of your applications in a cloud-native
            environment.
            """
            ),
        ),
        # Finalizer ignores the K8S agent's and Kyma agent's responses and answers the question itself
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(
                    content="what are the types of a k8s service? what is a kyma function?"
                ),
                AIMessage(
                    name="KubernetesAgent",
                    content="The sun emits light.",
                ),
                AIMessage(
                    name="KymaAgent",
                    content="The moon reflects the sun's light.",
                ),
            ],
            dedent(
                """
            In Kubernetes, there are several types of services that define how pods are exposed:
            1. **ClusterIP**: This is the default type. It exposes the service on a cluster-internal IP, making it accessible only within the cluster.
            2. **NodePort**: This type exposes the service on each node's IP at a static port. It makes the service accessible from outside the cluster using `<NodeIP>:<NodePort>`.
            3. **LoadBalancer**: This type is used in cloud environments to expose the service externally using a cloud provider's load balancer.
            4. **ExternalName**: This maps the service to the contents of the `externalName` field (e.g., `foo.bar.example.com`), returning a CNAME record with the name.
            A Kyma Function is a lightweight, serverless function that runs on the Kyma platform, which is built on top of
            Kubernetes. It allows developers to write code in a simple way to handle specific tasks or events without
            managing the underlying infrastructure. Kyma Functions are typically used for extending applications,
            integrating with external services, or automating workflows. They are managed and scaled automatically by
            the platform, making it easy to deploy and run code in response to events.
            """
            ),
        ),
        # Finalizer answers based on one of the agents' responses if another agent's response is invalid
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(
                    content="what is k8s stateful set and what is a kyma function?"
                ),
                AIMessage(
                    name="KubernetesAgent",
                    content="The sun emits light.",
                ),
                AIMessage(
                    name="KymaAgent",
                    content=dedent(
                        """
                A Kyma function is a lightweight, serverless function that runs in the Kyma environment. It allows you
                to execute custom business logic in response to events or HTTP requests. Functions are typically written
                in JavaScript or TypeScript and can be deployed easily within the Kyma ecosystem.
                Key features of Kyma functions include:
                1. **Event-Driven**: Functions can be triggered by various events, such as HTTP requests, messages from
                a message broker, or other events in the Kyma environment.
                2. **Scalability**: They automatically scale based on demand, allowing you to handle varying loads
                without manual intervention.
                3. **Integration**: Functions can easily integrate with other services and components in the Kyma
                ecosystem, such as APIs, databases, and external services.
                4. **Isolation**: Each function runs in its own isolated environment, ensuring that they do not
                interfere with each other.
                Overall, Kyma functions are a powerful way to extend the capabilities of your applications in a
                cloud-native environment.
                5. **Easy Deployment**: Functions can be deployed using the Kyma console, CLI, or CI/CD pipelines,
                making it straightforward to manage and update them.
                """
                    ),
                ),
            ],
            dedent(
                """
            Stateful sets are a type of Kubernetes resource that manage the deployment and scaling of stateful
            applications. They ensure that each instance of the application has its own persistent storage and can
            handle failures gracefully. Key features of StatefulSets include:
            1. **Stable Network Identity**: Each pod gets a persistent hostname with a predictable DNS name
            2. **Ordered Deployment**: Pods are created in sequential order (0,1,2) and scaled down in reverse order
            3. **Persistent Storage**: Each replica gets its own persistent volume that remains attached even after pod rescheduling
            4. **Stable Storage**: Storage volumes persist even when pods are deleted
            5. **Ordered Rolling Updates**: Updates are performed one pod at a time in a controlled manner
            StatefulSets are ideal for applications like databases, message queues, and other stateful workloads that require
            stable network identities and persistent storage.
            A Kyma function is a lightweight, serverless function that runs in the Kyma environment. It allows you to
            execute custom business logic in response to events or HTTP requests. Functions are typically written in
            JavaScript or TypeScript and can be deployed easily within the Kyma ecosystem.
            Key features of Kyma functions include:
            1. **Event-Driven**: Functions can be triggered by various events, such as HTTP requests, messages from a
            message broker, or other events in the Kyma environment.
            2. **Scalability**: They automatically scale based on demand, allowing you to handle varying loads without
            manual intervention.
            3. **Integration**: Functions can easily integrate with other services and components in the Kyma ecosystem,
            such as APIs, databases, and external services.
            4. **Isolation**: Each function runs in its own isolated environment, ensuring that they do not interfere
            with each other.
            5. **Easy Deployment**: Functions can be deployed using the Kyma console, CLI, or CI/CD pipelines, making it
            straightforward to manage and update them.
            Overall, Kyma functions are a powerful way to extend the capabilities of your applications in a cloud-native
            environment.
            """
            ),
        ),
        # Finalizer ignores irrelevant Kubernetes agent's response
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="write hello world Python script?"),
                AIMessage(
                    name="Common",
                    content=dedent(
                        """
                        Here is the hello world Python script:
                        ```python
                        print("Hello, World!")
                        ```
                        """
                    ),
                ),
                AIMessage(
                    name="KubernetesAgent",
                    content=dedent(
                        """
                    Here is how you can deploy your application using kubectl:
                    ```bash
                    kubectl apply -f deployment.yaml
                    ```
                    """
                    ),
                ),
            ],
            dedent(
                """
                Here is the hello world Python script:
                ```python
                print("Hello, World!")
                ```
                """
            ),
        ),
        # Finalizer answers based on Common and Kyma agent's responses
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(
                    content="write hello world nodejs script. Show me how to deploy it as a Kyma function."
                ),
                AIMessage(
                    name="Common",
                    content=dedent(
                        """
                        Here is the hello world nodejs script:
                        ```javascript
                        module.exports = {
                            main: function(event, context) {
                                return 'Hello World!'
                            }
                        }
                        ```
                        """
                    ),
                ),
                AIMessage(
                    name="KymaAgent",
                    content=dedent(
                        """
                    Here is how you can deploy the hello world nodejs script as a Kyma function:
                    You should define a function resource in the `function.yaml` file:
                    ```yaml
                    apiVersion: serverless.kyma-project.io/v1alpha2
                    kind: Function
                    metadata:
                      name: hello-world
                    spec:
                    runtime: nodejs20
                    source:
                      inline:
                        source: |
                          module.exports = {
                          main: function(event, context) {
                              return 'Hello World!'
                            }
                          }
                    ```
                    Then, you can deploy the function using the kubectl command:
                    ```bash
                    kubectl apply -f function.yaml
                    ```
                    """
                    ),
                ),
            ],
            dedent(
                """
                Here is the hello world nodejs script:
                ```javascript
                module.exports = {
                    main: function(event, context) {
                        return 'Hello World!'
                    }
                }
                ```
                Here is how you can deploy the hello world nodejs script as a Kyma function:
                You should define a function resource in the `function.yaml` file:
                ```yaml
                apiVersion: serverless.kyma-project.io/v1alpha2
                kind: Function
                metadata:
                  name: hello-world
                spec:
                runtime: nodejs20
                source:
                  inline:
                    source: |
                      module.exports = {
                      main: function(event, context) {
                          return 'Hello World!'
                        }
                      }
                ```
                Then, you can deploy the function using the kubectl command:
                ```bash
                kubectl apply -f function.yaml
                ```
                """
            ),
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(
                    content="what is the latest istio version included in Kyma?"
                ),
                AIMessage(
                    name="KymaAgent",
                    content="The latest Istio version included in Kyma is 1.24.1.",
                ),
            ],
            "The latest Istio version included in Kyma is 1.24.1.",
        ),
        (
            [
                SystemMessage(
                    content="The user query is related to: {'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="list me deployments in this namespace"),
                AIMessage(
                    name="KymaAgent",
                    content=dedent(
                        """
                        There is one deployment in the `nginx-oom` namespace:
                        
                        1. **Deployment Name:** nginx
                           - **Labels:** app: nginx
                           - **Replicas:** 1
                           - **Image:** nginx
                           - **Resource Limits:** 
                             - CPU: 250m
                             - Memory: 2Mi
                           - **Resource Requests:**
                             - CPU: 250m
                             - Memory: 1Mi
                           - **Environment Variables:**
                             - ACCESS_TOKEN: abcdefg
                        
                        The deployment is currently facing issues:
                        - **Available Status:** False
                          - **Reason:** MinimumReplicasUnavailable
                          - **Message:** Deployment does not have minimum availability.
                        - **Progressing Status:** False
                          - **Reason:** ProgressDeadlineExceeded
                          - **Message:** ReplicaSet "nginx-66b87d8476" has timed out progressing.
                        """
                    ),
                ),
            ],
            dedent(
                """
                There is one deployment in the `nginx-oom` namespace:

                1. **Deployment Name:** nginx
                   - **Labels:** app: nginx
                   - **Replicas:** 1
                   - **Image:** nginx
                   - **Resource Limits:** 
                     - CPU: 250m
                     - Memory: 2Mi
                   - **Resource Requests:**
                     - CPU: 250m
                     - Memory: 1Mi
                   - **Environment Variables:**
                     - ACCESS_TOKEN: abcdefg
                     
                The deployment is currently facing issues with availability and progress.
                """
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_final_response(
    messages, expected_answer, companion_graph, semantic_similarity_metric
):
    """
    Tests that the _generate_final_response method of the Finalizer correctly synthesizes
    the received agent responses or rejects irrelevant responses.
    """
    # Given: A conversation state with messages and an expected answer
    state = create_mock_state(messages)

    # When: The Finalizer generates a final response
    result = await companion_graph.supervisor_agent._generate_final_response(state)
    latest_human_message = next(
        msg.content for msg in reversed(messages) if isinstance(msg, HumanMessage)
    )
    test_case = LLMTestCase(
        input=latest_human_message,
        actual_output=result["messages"][0].content,
        expected_output=expected_answer,
    )

    # Then: We evaluate the response using deepeval metrics
    eval_results = evaluate(
        test_cases=[test_case],
        metrics=[
            semantic_similarity_metric,
        ],
    )
    assert all(
        result.success for result in eval_results.test_results
    ), "Not all metrics passed"
