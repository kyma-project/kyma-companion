from textwrap import dedent

import pytest
from deepeval import assert_test
from deepeval.test_case.llm_test_case import LLMTestCase
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from integration.agents.test_common_node import create_mock_state


@pytest.mark.parametrize(
    "test_case, messages, expected_answer",
    [
        (
            "case 1: Finalizer do not answer the question itself",
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="Describe Kyma in detail"),
                AIMessage(name="KymaAgent", content="It is a color of fish."),
            ],
            dedent(
                """It appears that the agents were unable to provide a detailed description of Kyma.
                    Therefore, I cannot offer any specific information on this topic.
                    If you have any other questions or need assistance with a different subject, feel free to ask!

                """
            ),
        ),
        (
            "case 2: Finalizer do not answer the question itself",
            [
                SystemMessage(
                    content="The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'test-namespace'}"
                ),
                HumanMessage(content="What is k8s?"),
                AIMessage(name="KubernetesAgent", content="The sky is blue."),
            ],
            dedent(
                """
            The agents did not provide any information regarding what Kubernetes (k8s) is.
            Therefore, I cannot offer any specific information on this topic.
            If you have any other questions or need assistance with a different subject, feel free to ask!
            """
            ),
        ),
        (
            "case 3: Finalizer do not answer the question itself",
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
                I'm sorry, but the agents did not provide any information regarding what Kubernetes (k8s) is.
                Therefore, I cannot offer any specific information on this topic.
                If you have any other questions or need assistance with a different subject, feel free to ask!
                """
            ),
        ),
        (
            "case 4: Finalizer do not answer the question itself",
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
                """The agents did not provide specific information regarding
                the types of Kubernetes services or the definition of a Kyma function.
                Therefore, I cannot offer any specific information on this topic.
                If you have any other questions or need assistance with a different subject, feel free to ask!
            """
            ),
        ),
        (
            "Finalizer answers based on Kyma agent's response",
            [
                SystemMessage(
                    content="The user query is related to: {'resource_kind': 'Cluster', 'resource_api_version': '', 'resource_name': '', 'resource_namespace': ''}"
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
        (
            "Finalizer answers based on K8S agent's response",
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
        (
            "Finalizer answers based on K8S and Kyma agents' responses",
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
        (
            "Finalizer answers based on one of the agents' responses if another agent's response is invalid",
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
                1. **Event-Driven**: Functions can be triggered by various events, such as HTTP requests, messages from a message broker, or other events in the Kyma environment.
                2. **Scalability**: They automatically scale based on demand, allowing you to handle varying loads without manual intervention.
                3. **Integration**: Functions can easily integrate with other services and components in the Kyma ecosystem, such as APIs, databases, and external services.
                4. **Isolation**: Each function runs in its own isolated environment, ensuring that they do not interfere with each other.
                Overall, Kyma functions are a powerful way to extend the capabilities of your applications in a cloud-native environment.
                5. **Easy Deployment**: Functions can be deployed using the Kyma console, CLI, or CI/CD pipelines, making it straightforward to manage and update them.
                """
                    ),
                ),
            ],
            dedent(
                """
                A Kyma function is a lightweight, serverless function that runs in the Kyma environment. It allows you
                to execute custom business logic in response to events or HTTP requests. Functions are typically written
                in JavaScript or TypeScript and can be deployed easily within the Kyma ecosystem.
                Key features of Kyma functions include:
                1. **Event-Driven**: Functions can be triggered by various events, such as HTTP requests, messages from a message broker, or other events in the Kyma environment.
                2. **Scalability**: They automatically scale based on demand, allowing you to handle varying loads without manual intervention.
                3. **Integration**: Functions can easily integrate with other services and components in the Kyma ecosystem, such as APIs, databases, and external services.
                4. **Isolation**: Each function runs in its own isolated environment, ensuring that they do not interfere with each other.
                Overall, Kyma functions are a powerful way to extend the capabilities of your applications in a cloud-native environment.
                5. **Easy Deployment**: Functions can be deployed using the Kyma console, CLI, or CI/CD pipelines, making it straightforward to manage and update them.
            """
            ),
        ),
        (
            "Finalizer answers based on Common and Kyma agent's responses",
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
            "finalizer answers short query based on Kyma agent's response",
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
            "finalizer answers query based on kubernetes agent's response",
            [
                SystemMessage(
                    content="The user query is related to: {'resource_namespace': 'nginx-oom'}"
                ),
                HumanMessage(content="list me deployments in this namespace"),
                AIMessage(
                    name="KubernetesAgent",
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
        (
            "Should mention about Joule context when kubenretes agent ask for resource name and namespace",
            [
                SystemMessage(
                    content="The user query is related to: {'resource_kind': 'Cluster' }"
                ),
                HumanMessage(content="Why is my pod in error state?"),
                AIMessage(
                    name="KubernetesAgent",
                    content=dedent(
                        """
                        To determine why your pod is in an error state, I need to know the specific pod name and its namespace. Joule enhances your workflow by using the active resource in your Kyma dashboard as the context for your queries.
                        This ensures that when you ask questions, Joule delivers relevant and tailored answers specific to the resource you're engaged with, making your interactions both efficient and intuitive.
                        """
                    ),
                ),
            ],
            dedent(
                """
                To determine why your pod is in an error state, I need to know the specific pod name and its namespace. Joule enhances your workflow by using the active resource in your Kyma dashboard as the context for your queries.
                This ensures that when you ask questions, Joule delivers relevant and tailored answers specific to the resource you're engaged with, making your interactions both efficient and intuitive.
                """
            ),
        ),
        (
            "Should mention about Joule context when kyma agent ask for resource name and namespace",
            [
                SystemMessage(
                    content="The user query is related to: {'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2'}"
                ),
                HumanMessage(
                    content="Why is the pod of the serverless Function not ready?"
                ),
                AIMessage(
                    name="KubernetesAgent",
                    content=dedent(
                        """
                        I need more information to answer this question. Please provide the name and namespace of the Function whose pod is not ready. This will help me investigate the specific issue and provide a solution tailored to your resource. 
                        Joule enhances your workflow by using the active resource in your Kyma dashboard as the context for your queries. This ensures that when you ask questions, Joule delivers relevant and tailored answers specific to the resource you're engaged with, making your interactions both efficient and intuitive.
                        """
                    ),
                ),
            ],
            dedent(
                """
                I need more information to answer this question. Please provide the name and namespace of the Function whose pod is not ready. This will help me investigate the specific issue and provide a solution tailored to your resource. 
                Joule enhances your workflow by using the active resource in your Kyma dashboard as the context for your queries. This ensures that when you ask questions, Joule delivers relevant and tailored answers specific to the resource you're engaged with, making your interactions both efficient and intuitive.
                """
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_final_response(
    test_case, messages, expected_answer, companion_graph, semantic_similarity_metric
):
    """
    Tests that the _generate_final_response method of the Finalizer correctly synthesizes
    the received agent responses or rejects irrelevant responses.
    """
    # Given: A conversation state with messages and an expected answer
    state = create_mock_state(messages)

    # When: The Finalizer generates a final response
    assert state.input is not None
    result = await companion_graph.supervisor_agent._generate_final_response(state)
    latest_human_message = HumanMessage(content=state.input.query)
    test_case = LLMTestCase(
        input=str(latest_human_message),
        actual_output=result["messages"][0].content,
        expected_output=expected_answer,
    )

    assert_test(test_case, [semantic_similarity_metric]), test_case
