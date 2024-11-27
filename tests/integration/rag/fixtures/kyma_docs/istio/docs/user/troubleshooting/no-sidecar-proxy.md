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
