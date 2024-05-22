# Enable Automatic Istio Sidecar Proxy Injection

Enabling automatic sidecar injection allows `istiod` to watch all Pod creation operations on all namespaces, which should be part of the Istio service mesh, and inject the newly created Pods with a sidecar proxy.

You can enable sidecar proxy injection for either an entire namespace or a single Deployment. If the sidecar proxy injection is disabled at the namespace level, or the `sidecar.istio.io/inject` label on a Pod is set to `false`, the sidecar proxy is not injected.

> [!NOTE]
>  Adding the `istio-injection=enabled` label on the namespace level results in injecting sidecars to all Pods inside of the namespace. 

* To enable sidecar proxy injection for a namespace, you can use either kubectl or Kyma dashboard:
  
  <!-- tabs:start -->

  #### **kubectl**
  
  Use the following command:
  
  ```bash
  kubectl label namespace {YOUR_NAMESPACE} istio-injection=enabled
  ```

  #### **Kyma Dashboard**
  
  1. Select the namespace where you want to enable sidecar proxy injection.
  2. Click **Edit**.
  3. In the `UI Form` section, set the **istio-injection** label value to `enabled` for the namespace.
  ![Switch the toggle to enable Istio sidecar injection](../../assets/sidecar-injection-toggle-namespace.svg)
  1. Click **Update**.
  <!-- tabs:end -->


* To enable sidecar proxy injection for a Pod, you can use either kubectl or Kyma dashboard:

  <!-- tabs:start -->

  #### **kubectl**
  
  Use the following command:
  
  ```bash
  kubectl patch -n {YOUR_NAMESPACE} deployments/{YOUR_DEPLOYMENT} -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"true"}}}}}'
  ```

  #### **Kyma Dashboard**

  1. Select the namespace of the Pod's Deployment.
  2. In the **Workloads** section, select **Deployments**.
  3. Select the Pod's Deployment and click **Edit**.
  4. In the `UI Form` section, set the **sidecar.istio.io/inject** label to `true`.
  ![Switch the toggle to enable Istio sidecar injection](../../assets/sidecar-injection-toggle-deployment.svg)
  1. Click **Update**.

  <!-- tabs:end -->