## Creating a Trace Pipeline in Kyma

This guide focuses on setting up a Trace Pipeline in Kyma, based on the provided markdown documentation. 

**1. Define your Trace Pipeline:**

Create a YAML file (e.g., `tracepipeline.yaml`) to define your TracePipeline resource. This configuration tells Kyma where to send your trace data.

* **Basic Configuration:**

```yaml
apiVersion: telemetry.kyma-project.io/v1alpha1
kind: TracePipeline
metadata:
  name: backend
spec:
  output:
    otlp:
      endpoint:
        value: https://backend.example.com:4317  # Replace with your backend endpoint
```

* **Protocol Selection:** The default protocol is GRPC (port 4317). To use HTTP (port 4318), add the `protocol` attribute:

```yaml
spec:
  output:
    otlp:
      protocol: http
      endpoint:
        value: https://backend.example.com:4318
```

**2. Add Authentication (if required):**

If your backend requires authentication, configure the `tracepipeline.yaml` to include credentials. You can use:

* **mTLS:** Provide certificate and key directly in the YAML or reference a Secret.
* **Basic Authentication:** Provide username and password directly or reference a Secret.
* **Token-based Authentication:**  Provide the token and any required headers directly or reference a Secret.

**3. Enable Istio Tracing:**

Istio is a key component for tracing in Kyma. To enable it, create a `Telemetry` resource in the `istio-system` namespace:

```yaml
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
  name: tracing-default
  namespace: istio-system
spec:
  tracing:
  - providers:
    - name: "kyma-traces"
    randomSamplingPercentage: 5.00  # Adjust sampling rate as needed
```

**4. Deploy the Trace Pipeline:**

Apply the `tracepipeline.yaml` file to your cluster:

```bash
kubectl apply -f tracepipeline.yaml
```

**5. Verify the Pipeline:**

Check the status of your TracePipeline:

```bash
kubectl get tracepipeline
```

Ensure all conditions (`CONFIGURATION GENERATED`, `GATEWAY HEALTHY`, `FLOW HEALTHY`) have the status `True`.

**Important Considerations:**

* **Sampling Rate:** Adjust the Istio sampling rate to balance data collection and resource usage.
* **Troubleshooting:** Refer to the "Troubleshooting" section of the documentation for common issues and solutions.
* **Limitations:** Be aware of the limitations regarding throughput, data loss, and system span filtering.

This guide provides a basic framework for creating a Trace Pipeline in Kyma. Remember to consult the full documentation for detailed information and advanced configuration options.
