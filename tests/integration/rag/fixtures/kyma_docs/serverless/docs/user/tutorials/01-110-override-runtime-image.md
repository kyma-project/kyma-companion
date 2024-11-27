# Override Runtime Image

This tutorial shows how to build a custom runtime image and override the Function's base image with it.

## Prerequisites

Before you start, make sure you have these tools installed:

- [Serverless module installed](https://kyma-project.io/docs/kyma/latest/04-operation-guides/operations/08-install-uninstall-upgrade-kyma-module/) in a cluster

## Steps

Follow these steps:

1. Follow [this example](https://github.com/kyma-project/serverless/tree/main/examples/custom-serverless-runtime-image) to build the Python's custom runtime image.

<!-- tabs:start -->

#### **Kyma CLI**

2. Export these variables:

    ```bash
    export NAME={FUNCTION_NAME}
    export NAMESPACE={FUNCTION_NAMESPACE}
    export RUNTIME_IMAGE={RUNTIME_IMAGE_WITH_TAG}
    ```

3. Create your local development workspace using the built image:

    ```bash
    mkdir {FOLDER_NAME}
    cd {FOLDER_NAME}
    kyma init function --name $NAME --namespace $NAMESPACE --runtime-image-override $RUNTIME_IMAGE --runtime python312
    ```

4. Deploy your Function:

    ```bash
    kyma apply function
    ```

5. Verify whether your Function is running:

    ```bash
    kubectl get functions $NAME -n $NAMESPACE
    ```

#### **kubectl**

2. Export these variables:

    ```bash
    export NAME={FUNCTION_NAME}
    export NAMESPACE={FUNCTION_NAMESPACE}
    export RUNTIME_IMAGE={RUNTIME_IMAGE_WITH_TAG}
    ```

3. Create a Function CR that specifies the Function's logic:

   ```bash
   cat <<EOF | kubectl apply -f -
   apiVersion: serverless.kyma-project.io/v1alpha2
   kind: Function
   metadata:
     name: $NAME
     namespace: $NAMESPACE
   spec:
     runtime: python312
     runtimeImageOverride: $RUNTIME_IMAGE
     source:
       inline:
         source: |
           module.exports = {
             main: function(event, context) {
               return 'Hello World!'
             }
           }
   EOF
   ```

4. Verify whether your Function is running:

    ```bash
    kubectl get functions $NAME -n $NAMESPACE
    ```

<!-- tabs:end -->
