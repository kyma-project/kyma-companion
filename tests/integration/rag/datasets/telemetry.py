from textwrap import dedent

cases = [
    {
        "input": "show how to create a trace pipeline",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
                To create a trace pipeline in Kyma, follow these steps:

                1. Create a resource of the kind `TracePipeline` and save it in a file named, for example, `tracepipeline.yaml`. 

                2. Configure the pipeline for traces. Here are examples for both GRPC and HTTP protocols:

                  - For GRPC:
                  ```yaml
                  apiVersion: telemetry.kyma-project.io/v1alpha1
                  kind: TracePipeline
                  metadata:
                    name: backend
                  spec:
                    output:
                      otlp:
                        endpoint:
                          value: https://backend.example.com:4317
                  ```

                  - For HTTP:
                  ```yaml
                  apiVersion: telemetry.kyma-project.io/v1alpha1
                  kind: TracePipeline
                  metadata:
                    name: backend
                  spec:
                    output:
                      otlp:
                        protocol: http
                        endpoint:
                          value: https://backend.example.com:4318
                  ```

                3. To activate the TracePipeline, apply the `tracepipeline.yaml` resource file in your cluster:
                  ```bash
                  kubectl apply -f tracepipeline.yaml
                  ```

                4. Check that the pipeline is running by verifying the status conditions:
                  ```bash
                  kubectl get tracepipeline
                  ```

                Make sure the status shows `True` for the relevant conditions.
                                """
        ),
    },
    # "fixtures/kyma_docs/telemetry-manager/docs/user/02-logs.md"
    {
        "input": "How to configure Kyma application logging?",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
            '# Auditing and Logging Information in Kyma - Application Logs of System Components\nKyma runtime collects application logs provided by the Kyma system components. Those logs reflect regular events that occurred in Kyma runtime and must not include any personal or sensitive data. These are typically system-related activities and operations you can analyze to get more information about performance or to inspect potential problems.\n**Related Information**\n[https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)\n[Audit Logging in the Cloud Foundry Environment](https://help.sap.com/viewer/65de2977205c403bbc107264b8eccf4b/Cloud/en-US/f92c86ab11f6474ea5579d839051c334.html)\n[Audit Logging in the Neo Environment](https://help.sap.com/viewer/ea72206b834e4ace9cd834feed6c0e09/Cloud/en-US/02c39712c1064c96b37c1ea5bc9420dc.html)\n[Access Kyma Application Logs](../50-administration-and-ops/access-kyma-application-logs-25180f4.md "Get insights into your applications, microservices, and Functions by viewing the respective logs. To check out real-time logs immediately, use the Kubernetes functionalities - either in Kyma dashboard, or with kubectl.")\n[Collecting Logs](../30-development/collecting-logs-7a5b627.md "With the Telemetry module, you can observe and debug your applications by collecting, processing, and exporting logs. To begin collecting logs, you create a LogPipeline resource. It automatically collects OTLP logs and application logs from the stdout/stderr channel. You can also activate Istio log collection.")'
            """
        ),
    },
    {
        "input": "why are there no logs in the backend?",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
                ### No Logs Arrive at the Backend

                **Symptom**:

                - No logs arrive at the backend.
                - In the LogPipeline status, the `TelemetryFlowHealthy` condition has status **AllDataDropped**.

                **Cause**: Incorrect backend endpoint configuration (for example, using the wrong authentication credentials) or the backend being unreachable.

                **Remedy**:

                - Check the `telemetry-fluent-bit` Pods for error logs by calling `kubectl logs -n kyma-system {POD_NAME}`.
                - Check if the backend is up and reachable.
                """
        ),
    },
]
