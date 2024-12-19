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
        "input": "what are the prerequisites for Kyma application to enable logging?",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
                One of the **rerequisites** for an application to be able to log is:

                * **Log to `stdout` or `stderr`:** Your application must write its log messages to the standard output (`stdout`) or standard error (`stderr`) streams. This is essential because Kubernetes uses these streams to collect and manage container logs.
                """
        ),
    },
    {
        "input": "why there is no logs in the backend?",
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
