import pytest
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from integration.agents.test_common_node import create_mock_state


@pytest.mark.parametrize(
    "messages, expected_answer",
    [
        # Invoke Kyma agent:
        # - Simulate valid answers
        # - Simulate invalid answers
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                ),
                HumanMessage(content="What is Kyma?"),
                AIMessage(
                    name="KymaAgent",
                    content="""
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
                """,
                ),
            ],
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
            """,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                ),
                HumanMessage(content="What is Kyma?"),
                AIMessage(name="KymaAgent", content="It is a color of fish."),
            ],
            "I apologize, but I am unable to provide an answer to your query at the moment.",
        ),
        # Invoke K8S agent:
        # - Simulate valid answers
        # - Simulate invalid answers
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                ),
                HumanMessage(content="What is k8s?"),
                AIMessage(
                    name="KubernetesAgent",
                    content="""
                Kubernetes, often abbreviated as K8s, is an open-source platform designed to automate deploying,
                scaling, and operating application containers. Originally developed by Google, it is now maintained by
                the Cloud Native Computing Foundation (CNCF). Kubernetes provides a framework to run distributed systems
                resiliently, taking care of scaling and failover for your application, providing deployment patterns,
                and more.
                Key features of Kubernetes include:
                1. **Automated Rollouts and Rollbacks**: Kubernetes can manage the deployment of changes to your
                application or its configuration, ensuring that not all instances are updated simultaneously, and can
                roll back changes if something goes wrong.
                2. **Service Discovery and Load Balancing**: Kubernetes can expose a container using the DNS name or
                their own IP address. If traffic to a container is high, Kubernetes can load balance and distribute the
                network traffic so that the deployment is stable.
                3. **Storage Orchestration**: Kubernetes allows you to automatically mount the storage system of your
                choice, such as local storage, public cloud providers, and more.
                4. **Self-Healing**: Kubernetes restarts containers that fail, replaces containers, kills containers
                that don’t respond to your user-defined health check, and doesn’t advertise them to clients until they
                are ready to serve.
                5. **Secret and Configuration Management**: Kubernetes lets you store and manage sensitive information,
                such as passwords, OAuth tokens, and ssh keys. You can deploy and update secrets and application
                configuration without rebuilding your image and without exposing secrets in your stack configuration.
                Kubernetes is highly extensible and can be used to manage containerized applications across various
                environments, from on-premises data centers to public clouds.
                """,
                ),
            ],
            """
            Kubernetes, often abbreviated as K8s, is an open-source platform designed to automate deploying, scaling,
            and operating application containers. Originally developed by Google, it is now maintained by the Cloud
            Native Computing Foundation (CNCF). Kubernetes provides a framework to run distributed systems resiliently,
            taking care of scaling and failover for your application, providing deployment patterns, and more.
            Key features of Kubernetes include:
            1. **Automated Rollouts and Rollbacks**: Kubernetes can manage the deployment of changes to your application
            or its configuration, ensuring that not all instances are updated simultaneously, and can roll back changes
            if something goes wrong.
            2. **Service Discovery and Load Balancing**: Kubernetes can expose a container using the DNS name or their
            own IP address. If traffic to a container is high, Kubernetes can load balance and distribute the network
            traffic so that the deployment is stable.
            3. **Storage Orchestration**: Kubernetes allows you to automatically mount the storage system of your
            choice, such as local storage, public cloud providers, and more.
            4. **Self-Healing**: Kubernetes restarts containers that fail, replaces containers, kills containers that
            don’t respond to your user-defined health check, and doesn’t advertise them to clients until they are ready
            to serve.
            5. **Secret and Configuration Management**: Kubernetes lets you store and manage sensitive information, such
            as passwords, OAuth tokens, and ssh keys. You can deploy and update secrets and application configuration
            without rebuilding your image and without exposing secrets in your stack configuration.
            Kubernetes is highly extensible and can be used to manage containerized applications across various
            environments, from on-premises data centers to public clouds.
            """,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                ),
                HumanMessage(content="What is k8s?"),
                AIMessage(name="KubernetesAgent", content="The sky is blue."),
            ],
            "I apologize, but I am unable to provide an answer to your query at the moment.",
        ),
        # Invoke K8S and Kyma agents:
        # - Simulate two valid answers
        # - Simulate two invalid answers
        # - Simulate one valid and one invalid answer
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                ),
                HumanMessage(
                    content="what are the types of a k8s service? what is a kyma function?"
                ),
                AIMessage(
                    name="KubernetesAgent",
                    content="""
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
                """,
                ),
                AIMessage(
                    name="KymaAgent",
                    content="""
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
                """,
                ),
            ],
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
            """,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
                ),
                HumanMessage(
                    content="what are the types of a k8s service? what is a kyma function?"
                ),
                AIMessage(
                    name="KubernetesAgent",
                    content="""
                The sun emits light.
                """,
                ),
                AIMessage(
                    name="KymaAgent",
                    content="""
                The moon reflects the sun's light.
                """,
                ),
            ],
            """
            I apologize, but I am unable to provide an answer to your query at the moment.
            """,
        ),
        (
            [
                SystemMessage(
                    content="""
                The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                """
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
                    content="""
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
                """,
                ),
            ],
            """
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

            I apologize, but I am unable to provide an answer to your Kubernetes question at the moment.
            """,
        ),
    ],
)
def test_invoke_finalizer(
    messages, expected_answer, companion_graph, semantic_similarity_metric
):
    """Tests the _generate_final_response method of SupervisorAgent"""
    state = create_mock_state(messages)

    result = companion_graph.supervisor_agent._generate_final_response(state)

    latest_human_message = next(
        msg.content for msg in reversed(messages) if isinstance(msg, HumanMessage)
    )

    test_case = LLMTestCase(
        input=latest_human_message,
        actual_output=result["messages"][0].content,
        expected_output=expected_answer,
    )

    # assert_test(test_case, [semantic_similarity_metric])

    # Run deepeval metrics
    eval_results = evaluate(
        test_cases=[test_case],
        metrics=[
            semantic_similarity_metric,
        ],
    )

    # Assert all metrics pass
    assert all(
        result.success for result in eval_results.test_results
    ), "Not all metrics passed"
