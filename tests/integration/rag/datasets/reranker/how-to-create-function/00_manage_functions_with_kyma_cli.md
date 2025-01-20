# Manage Functions with Kyma CLI
This tutorial shows how to use the available CLI commands to manage Functions in Kyma. You will see how to:
1. Create local files that contain the basic configuration for a sample "Hello World" Python Function (`kyma init function`).
2. Generate a Function custom resource (CR) from these files and apply it on your cluster (`kyma apply function`).
3. Fetch the current state of your Function's cluster configuration after it was modified (`kyma sync function`).
> [!NOTE]
> Read about [Istio sidecars in Kyma and why you want them](https://kyma-project.io/docs/kyma/latest/01-overview/service-mesh/smsh-03-istio-sidecars-in-kyma/). Then, check how to [enable automatic Istio sidecar proxy injection](https://kyma-project.io/docs/kyma/latest/04-operation-guides/operations/smsh-01-istio-enable-sidecar-injection/). For more details, see [Default Istio setup in Kyma](https://kyma-project.io/docs/kyma/latest/01-overview/service-mesh/smsh-02-default-istio-setup-in-kyma/).
This tutorial is based on a sample Python Function run in a lightweight [k3d](https://k3d.io/) cluster.