## Local k3d setup for the local lifecycle-manager & Keda Manager

1. Clone the project.

   ```bash
   git clone https://github.com/kyma-project/keda-manager.git && cd keda-manager/
   ```

2. Provide the k3d cluster.

   ```bash
   kyma provision k3d
   ```

3. Build and push the Keda Manager image.

   ```bash
   make module-image IMG_REGISTRY=localhost:5001/unsigned/operator-images IMG=localhost:5001/keda-manager-dev-local:0.0.1
   ```

4. Build and push the Keda module.

   ```bash
   make module-build IMG=k3d-kyma-registry:5001/keda-manager-dev-local:0.0.1 MODULE_REGISTRY=localhost:5001/unsigned
   ```

5. Verify if the module and the manager's image are pushed to the local registry.

   ```bash
   curl localhost:5001/v2/_catalog
   ```
You should get a result similar to this example:

   ```json
   {"repositories":["keda-manager-dev-local","unsigned/component-descriptors/kyma-project.io/module/keda"]}
   ```
6. Inspect the generated module template.

> **NOTE:** The following sub-steps are temporary workarounds.

Edit `template.yaml` and:
- change `target` to `control-plane`

   ```yaml
   spec:
    target: control-plane
    ```
> **NOTE:** This is required in the single-cluster mode only.

- change the existing repository context in `spec.descriptor.component`:

   ```yaml
   repositoryContexts:      
     - baseUrl: k3d-kyma-registry.localhost:5000/unsigned
       componentNameMapping: urlPath
       type: ociRegistry
   ```


7. Install the modular Kyma on the k3d cluster.

> **NOTE** This installs the latest versions of `lifecycle-manager`.

Use the `--template` flag to deploy the Keda module manifest from the beggining, or apply it using kubectl later.

   ```bash
   kyma alpha deploy --template=./template.yaml
   ```
Kyma installation is ready, but the module is not yet activated.

   ```bash
   kubectl get kymas.operator.kyma-project.io -A
   ```
You should get a result similar to the following example:

   ```bash
   NAMESPACE    NAME           STATE   AGE
   kcp-system   default-kyma   Ready   71s
   ```

Keda module is a known module, but not yet activated.

   ```bash
   kubectl get moduletemplates.operator.kyma-project.io -A 
   ```

You should get a result similar to the following example:

   ```bash
   NAMESPACE    NAME                  AGE
   kcp-system   moduletemplate-keda   2m24s
   ```

8.  Give Module Manager permission to install CRD cluster-wide.

> **NOTE:** `module-manager` must be able to apply CRDs to install modules. In the remote mode (with control-plane managing remote clusters) it gets an administrative kubeconfig, targeting the remote cluster to do so. But in the local mode (single-cluster mode), it uses Service Account and does not have permission to create CRDs by default.

Run the following to make sure Module Manager's Service Account gets an administrative role:

   ```bash
   kubectl edit clusterrole module-manager-manager-role
   ```

Add the following element under `rules`:

   ```yaml
   - apiGroups:
     - "*"
     resources:
     - "*"                  
     verbs:                  
     - "*"
  ```

> **NOTE:** This is a temporary workaround and is only required in the single-cluster mode.

9. Enable Keda in the Kyma custom resource (CR).

   ```bash
   kubectl edit kymas.operator.kyma-project.io -n kcp-system default-kyma
   ```

   Add the following field under `spec`:

   ```yaml
     modules:
     - name: keda
       channel: alpha
  ```

