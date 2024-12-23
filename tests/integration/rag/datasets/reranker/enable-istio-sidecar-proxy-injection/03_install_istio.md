# Install Istio

## Prerequisites

- Access to a Kubernetes cluster (you can use [k3d](https://k3d.io/v5.5.1/))
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [kubebuilder](https://book.kubebuilder.io/)
- [Docker](https://www.docker.com)
- [Kyma CLI](https://github.com/kyma-project/cli/blob/main/README.md#installation)

## Install Kyma Istio Operator Manually

1. Clone the project.

```bash
git clone https://github.com/kyma-project/istio.git && cd istio
```

2. Set the Istio Operator image name.

```bash
export IMG=istio-operator:0.0.1
export K3D_CLUSTER_NAME=kyma
```

3. Provision the k3d cluster.

```bash
k3d registry create kyma-registry --port 5001
k3d cluster create kyma --kubeconfig-switch-context -p 80:80@loadbalancer -p 443:443@loadbalancer  --k3s-arg "--disable=traefik@server:0" --registry-use kyma-registry
kubectl create ns kyma-system
```
>**TIP:** To verify the correctness of the project, build it using the `make build` command.

4. Build the image.

Run:
```bash
make docker-build
```

To build the experimental image, run:
```bash
make docker-build-experimental
```

5. Push the image to the registry.

<div tabs name="Push image" group="istio-operator-installation">
  <details>
  <summary label="k3d">
  k3d
  </summary>

   ```bash
   k3d image import $IMG -c $K3D_CLUSTER_NAME
   ```

  </details>
  <details>
  <summary label="Docker registry">
  Globally available Docker registry
  </summary>

   ```bash
   make docker-push
   ```

  </details>
</div>

6. Deploy Istio Operator.

```bash
make deploy
```

### Use Kyma Istio Operator to Install or Uninstall Istio

- Install Istio in your cluster.

```bash
kubectl apply -f config/samples/operator_v1alpha2_istio.yaml
```

- Delete Istio from your cluster.

```bash
kubectl delete -f config/samples/operator_v1alpha2_istio.yaml
```
