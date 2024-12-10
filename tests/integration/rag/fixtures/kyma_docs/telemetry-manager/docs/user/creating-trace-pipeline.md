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