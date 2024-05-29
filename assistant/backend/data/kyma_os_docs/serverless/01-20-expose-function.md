# Expose a Function with an API Rule

This tutorial shows how you can expose your Function to access it outside the cluster, through an HTTP proxy. To expose it, use an [APIRule custom resource (CR)](https://kyma-project.io/docs/kyma/latest/05-technical-reference/00-custom-resources/apix-01-apirule/). Function Controller reacts to an instance of the APIRule CR and, based on its details, it creates an Istio VirtualService and Oathkeeper Access Rules that specify your permissions for the exposed Function.

When you complete this tutorial, you get a Function that:

- Is available on an unsecured endpoint (**handler** set to `noop` in the APIRule CR).
- Accepts the `GET`, `POST`, `PUT`, and `DELETE` methods.

To learn more about securing your Function, see the [Expose and secure a workload with OAuth2](https://kyma-project.io/docs/kyma/latest/03-tutorials/00-api-exposure/apix-05-expose-and-secure-a-workload/apix-05-01-expose-and-secure-workload-oauth2/) or [Expose and secure a workload with JWT](https://kyma-project.io/docs/kyma/latest/03-tutorials/00-api-exposure/apix-05-expose-and-secure-a-workload/apix-05-03-expose-and-secure-workload-jwt/) tutorials.

Read also about [Function’s specification](../technical-reference/07-70-function-specification.md) if you are interested in its signature, `event` and `context` objects, and custom HTTP responses the Function returns.

## Prerequisites

- [Existing Function](01-10-create-inline-function.md)
- [API Gateway component installed](https://kyma-project.io/docs/kyma/latest/04-operation-guides/operations/02-install-kyma/#install-specific-components) 

## Steps

You can expose a Function with Kyma dashboard, Kyma CLI, or kubectl:

<!-- tabs:start -->

#### **Kyma Dashboard**

> [!NOTE]
> Kyma dashboard uses Busola, which is not installed by default. Follow the [installation instructions](https://github.com/kyma-project/busola/blob/main/docs/install-kyma-dashboard-manually.md).

1. Select a namespace from the drop-down list in the top navigation panel. Make sure the namespace includes the Function that you want to expose through an APIRule.

2. Go to **Discovery and Network** > **API Rules**, and click on **Create API Rule**.

3. Enter the following information:

    - The APIRule's **Name** matching the Function's name.

    > [!NOTE]
    > The APIRule CR can have a name different from that of the Function, but it is recommended that all related resources share a common name.

    - **Service Name** matching the Function's name.

    - **Host** to determine the host on which you want to expose your Function. You must change the `*` symbol at the beginning to the subdomain name you want.

4. In the **Rules > Access Strategies > Config**  section, change the handler from `allow` to `noop` and select all the methods below.

5. Select **Create** to confirm your changes.

6. Check if you can access the Function by selecting the HTTPS link under the **Host** column for the newly created APIRule.

#### **Kyma CLI**

1. Export these variables:

      ```bash
      export DOMAIN={DOMAIN_NAME}
      export NAME={FUNCTION_NAME}
      export NAMESPACE={NAMESPACE_NAME}
      ```
   > [!NOTE]
   > The Function takes the name from the Function CR name. The APIRule CR can have a different name but for the purpose of this tutorial, all related resources share a common name defined under the **NAME** variable.
2. Download the latest configuration of the Function from the cluster. This way, you update the local `config.yaml` file with the Function's code.

  ```bash
  kyma sync function $NAME -n $NAMESPACE
  ```

3. Edit the local `config.yaml` file and add the **apiRules** schema for the Function at the end of the file:

  ```yaml
  apiRules:
      - name: {FUNCTION_NAME}
        service:
          host: {FUNCTION_NAME}.{DOMAIN_NAME}
        rules:
          - methods:
              - GET
              - POST
              - PUT
              - DELETE
            accessStrategies:
              - handler: noop
  ```

4. Apply the new configuration to the cluster:

  ```bash
  kyma apply function
  ```

5. Check if the Function's code was pushed to the cluster and reflects the local configuration:

  ```bash
  kubectl get apirules $NAME -n $NAMESPACE
  ```

6. Check that the APIRule was created successfully and has the status `OK`:

  ```bash
  kubectl get apirules $NAME -n $NAMESPACE -o=jsonpath='{.status.APIRuleStatus.code}'
  ```

7. Call the Function's external address:

  ```bash
  curl https://$NAME.$DOMAIN
  ```

#### **kubectl**

1. Export these variables:

    ```bash
    export DOMAIN={DOMAIN_NAME}
    export NAME={FUNCTION_NAME}
    export NAMESPACE={FUNCTION_NAMESPACE}
    ```

    > [!NOTE]
    > The Function takes the name from the Function CR name. The APIRule CR can have a different name but for the purpose of this tutorial, all related resources share a common name defined under the **NAME** variable.

2. Create an APIRule CR for your Function. It is exposed on port `80`, which is the default port of the [Service Placeholder](../technical-reference/04-10-architecture.md).

    ```bash
    cat <<EOF | kubectl apply -f -
    apiVersion: gateway.kyma-project.io/v1beta1
    kind: APIRule
    metadata:
      name: $NAME
      namespace: $NAMESPACE
    spec:
      gateway: kyma-system/kyma-gateway
      host: $NAME.$DOMAIN
      rules:
      - path: /.*
        accessStrategies:
        - config: {}
          handler: noop
        methods:
        - GET
        - POST
        - PUT
        - DELETE
      service:
        name: $NAME
        port: 80
    EOF
    ```

3. Check that the APIRule was created successfully and has the status `OK`:

    ```bash
    kubectl get apirules $NAME -n $NAMESPACE -o=jsonpath='{.status.APIRuleStatus.code}'
    ```

4. Access the Function's external address:

    ```bash
    curl https://$NAME.$DOMAIN
    ```

<!-- tabs:end -->