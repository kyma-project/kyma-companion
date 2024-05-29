# Check If You Have Istio Sidecar Proxy Injection Enabled

## Check If Sidecar Injection Is Enabled in the Pod's Namespace

<!-- tabs:start -->

#### **kubectl**
To check if the Pod's namespace is labeled with `istio-injection=enabled`, run:

  ```bash
  kubectl get namespaces {NAMESPACE} -o jsonpath='{ .metadata.labels.istio-injection }'
  ```
If the command does not return `enabled`, the sidecar injection is disabled in this namespace.

#### **Kyma Dashboard**

1. Go to the Pod's namespace.
2. Verify if the `Labels` section contains `istio-injection=enabled`. If the section doesn't contain the label, the sidecar injection is disabled in this namespace.
   Here's an example of a namespace where the Istio sidecar proxy injection is enabled:
   ![Namespace with enabled Istio sidecar injection](../../assets/namespace-with-enabled-istio-sidecar.svg)

<!-- tabs:end -->

## Check If Sidecar Injection Is Enabled for the Pod's Deployment

<!-- tabs:start -->

#### **kubectl**

To check if sidecar injection is enabled, run:

  ```bash
  kubectl get deployments {DEPLOYMENT_NAME} -n {NAMESPACE} -o jsonpath='{ .spec.template.metadata.labels }'
  ```
If the output does not contain the `sidecar.istio.io/inject:true` line, sidecar injection is disabled.

#### **Kyma Dashboard**

1. Select the namespace of the Pod's Deployment.
2. In the **Workloads** section, select **Deployments**.
3. Select the Pod's Deployment and click **Edit**.
4. In the `UI Form` section, check if the `Enable Sidecar Injection` toggle is switched.
    ![Check the enable Istio sidecar toggle](../../assets/sidecar-injection-toggle-deployment.svg)

<!-- tabs:end -->


## List All Pods with Sidecar Injection Enabled

You can also check whether your workloads have automatic Istio sidecar injection enabled by running [the script](../../assets/sidecar-analysis.sh). Either pass the **namespace** parameter to the script or run it with no parameter.

* If you don't provide any parameter, the execution output contains Pods from all namespaces that don't have automatic Istio sidecar injection enabled. The script outputs the information in the format of `{NAMESPACE}/{POD}`. Run:

    ```bash
    ./sidecar-analysis.sh
    ```

  You get an output similar to this one:

    ```
    Pods out of istio mesh:
      In namespace labeled with "istio-injection=disabled":
        - sidecar-disabled/some-pod
      In namespace labeled with "istio-injection=enabled" with pod labeled with "sidecar.istio.io/inject=false":
        - sidecar-enabled/some-pod
      In not labeled ns with pod not labeled with "sidecar.istio.io/inject=true":
        - no-label/some-pod
    ```

*  If you pass a parameter, only the Pods from the specified namespace are analyzed. The script outputs the information in the format of `{POD}`. Run:

    ```bash
    ./sidecar-analysis.sh {NAMESPACE}
    ```
    You get an output similar to this one:

    ```
    Pods out of istio mesh in namespace {NAMESPACE}:
      - some-pod
    ```

For more information, see the [Sidecar injection problems](https://istio.io/docs/ops/common-problems/injection/).