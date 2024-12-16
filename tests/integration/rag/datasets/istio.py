from textwrap import dedent

cases = [
    {
        "input": "How to enable Istio sidecar proxy injection?",
        "expected_output": dedent(
            """
            Istio sidecar proxy injection can be enabled in two ways:

            ## Prerequisites
            - Istio module must be added
            - kubectl installed (for CLI method) or access to Kyma dashboard

            ## Namespace-Level Injection
            **Using Kyma Dashboard:**
            1. Select target namespace
            2. Click Edit
            3. Enable Istio sidecar proxy injection toggle in UI Form
            4. Save changes

            **Using kubectl:**
            ```bash
            kubectl label namespace {YOUR_NAMESPACE} istio-injection=enabled
            ```

            ## Deployment-Level Injection
            **Using Kyma Dashboard:**
            1. Select namespace
            2. Go to Workloads > Deployments
            3. Select target Deployment
            4. Click Edit
            5. Enable Istio sidecar proxy injection toggle in UI Form
            6. Save changes

            **Using kubectl:**
            ```bash
            kubectl patch -n {YOUR_NAMESPACE} deployments/{YOUR_DEPLOYMENT} -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"true"}}}}}'
            ```

            ## Known Limitations
            The sidecar proxy will not be injected if:
            - Namespace-level injection is disabled
            - Pod has `sidecar.istio.io/inject: false` label
            - Pod spec includes `hostNetwork: true`

            ## Results
            - For namespace: All new Pods in the namespace will get the sidecar proxy
            - For deployment: All Pods in the deployment get instantly injected with the sidecar proxy
            """
        ),
    },
    {
        "input": "why an Istio sidecar is not injected to a pod?",
        "expected_output": dedent(
            """
            ### Problem
            Istio sidecar proxy is not injected into a Pod.

            ### Causes of Failed Sidecar Injection

            A Pod will not receive an Istio sidecar proxy injection under these conditions:
            - The namespace has Istio sidecar proxy injection disabled
            - The Pod has the `sidecar.istio.io/inject` label explicitly set to `false`
            - The Pod specification includes `hostNetwork: true`

            ### Solutions

            **Namespace-Level Injection**
            - Using Kyma Dashboard:
              1. Navigate to the target namespace
              2. Click "Edit"
              3. Enable Istio sidecar proxy injection using the toggle in UI Form
              4. Save changes

            - Using kubectl:
            ```bash
            kubectl label namespace {YOUR_NAMESPACE} istio-injection=enabled
            ```

            **Deployment-Level Injection**
            - Using Kyma Dashboard:
              1. Navigate to the target namespace
              2. Go to Workloads > Deployments
              3. Select the deployment
              4. Click "Edit"
              5. Enable Istio sidecar proxy injection using the toggle in UI Form
              6. Save changes

            - Using kubectl:
            ```bash
            kubectl patch -n {YOUR_NAMESPACE} deployments/{YOUR_DEPLOYMENT} -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"true"}}}}}'
            ```

            **Prerequisites**
            - Istio module must be added to your Kyma installation
            - kubectl must be installed for CLI operations (optional if using Kyma dashboard)

            After applying either solution, the affected resources will be labeled with `istio-injection: enabled`. For namespace-level injection, all new Pods in the namespace will receive the sidecar proxy. For deployment-level injection, all Pods in the deployment will be immediately injected with the Istio sidecar proxy.
            """
        ),
    },
    {
        "input": "Why do I get a 'Connection reset by peer' error?",
        # "Why do I get a connection refuses error?",
        "expected_output": dedent(
            """
            ### Problem
            You receive a 'Connection reset by peer' error when attempting to establish a connection between a service without a sidecar and a service with a sidecar.

            ### Cause
            This error occurs because mutual TLS (mTLS) is enabled by default in the service mesh, requiring every element to have an Istio sidecar with a valid TLS certificate for communication.

            ### Solution
            1. **Add the service without a sidecar to the allowlist and disable mTLS traffic for it**:
              - Create a `DestinationRule` resource.
              - Refer to the [DestinationRule documentation](https://istio.io/docs/reference/config/networking/destination-rule/) for details.

            2. **Allow connections between the service without a sidecar and the service with a sidecar**:
              - Create a `PeerAuthentication` resource in `PERMISSIVE` mode.
              - Refer to the [Peer Authentication documentation](https://istio.io/latest/docs/reference/config/security/peer_authentication/) for details.
            """
        ),
    },
    {
        "input": "function pod have have no sidecar proxy",
        # "fixtures/kyma_docs/istio/docs/user/troubleshooting/03-30-istio-no-sidecar.md",
        "expected_output": dedent(
            """
            If your Kyma function doesn't have an Istio sidecar proxy injected, it could be due to a few reasons:

            1. **Namespace-level Injection Disabled:**

              - The namespace where your function resides might have Istio sidecar injection explicitly disabled. This is often done intentionally to exclude certain namespaces from the service mesh.
              - You can check this using the Kyma Dashboard by looking for the `istio-injection=disabled` label in the namespace's **Labels** section.
              - Alternatively, use `kubectl`: `kubectl get namespaces {POD_NAMESPACE} -o jsonpath='{ .metadata.labels.istio-injection }'`.

            2. **`sidecar.istio.io/inject` Label Set to `false`:**

              - The Pod associated with your function might have the `sidecar.istio.io/inject` label explicitly set to `false`. This overrides any namespace-level settings and prevents injection.
              - Check this in the Kyma Dashboard under **Workloads** > **Pods** by searching for `sidecar.istio.io/inject: false`.
              - Or use `kubectl`: `kubectl get pod {POD} -n default -o=jsonpath='{.metadata.labels.sidecar\.istio\.io/inject}'`.

            3. **`hostNetwork: true` in Pod Spec:**

              - If your function's Pod definition includes `hostNetwork: true`, the sidecar proxy won't be injected. This setting configures the Pod to use the host's network namespace, which is incompatible with Istio's traffic management.
              - You'll need to examine the Pod's specification to confirm this.

            **Solution:**

            To enable sidecar injection, you need to address the specific cause:

            - **Enable namespace-level injection:** If your namespace has injection disabled, you can enable it using the Kyma Dashboard or `kubectl`.
            - **Remove or correct the `sidecar.istio.io/inject` label:** Ensure the label is set to `true` or removed entirely to allow injection.
            - **Avoid using `hostNetwork: true`:** If possible, reconfigure your function to avoid this setting.

            For detailed instructions on enabling sidecar injection, refer to the Kyma documentation on "Enabling Istio Sidecar Proxy Injection."
            """
        ),
    },
]
