To expose a Kyma function using the APIRule custom resource, you have three options:

**1. Kyma Dashboard:**

- Navigate to **Discovery and Network** > **API Rules** and click **Create API Rule**.
- Provide the APIRule name (matching the function's name is recommended), service name, and desired host.
- In **Rules** > **Access Strategies**, select methods (GET, POST, PUT, DELETE) and the `no_auth` handler for an unsecured endpoint.
- Click **Create** and test the exposed function using the HTTPS link under the **Host** column.


**2. Kyma CLI:**

- Export `DOMAIN`, `NAME` (function name), and `NAMESPACE`.
- Download the function's configuration: `kyma sync function $NAME -n $NAMESPACE`.
- Edit `config.yaml` to include the `apiRules` schema:

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
          - handler: no_auth
```

- Apply the configuration: `kyma apply function`.
- Verify the APIRule creation and status: `kubectl get apirules $NAME -n $NAMESPACE` and `kubectl get apirules $NAME -n $NAMESPACE -o=jsonpath='{.status.APIRuleStatus.code}'`.
- Call the function's external address: `curl https://$NAME.$DOMAIN`.


**3. kubectl:**

- Export `DOMAIN`, `NAME`, and `NAMESPACE`.
- Create an APIRule CR using `kubectl apply -f -` with the following YAML structure:

```yaml
apiVersion: gateway.kyma-project.io/v1beta1
kind: APIRule
metadata:
  name: $NAME
  namespace: $NAMESPACE
spec:
  gateway: kyma-system/kyma-gateway
  host: $NAME.$DOMAIN
  service:
    name: $NAME
    port: 80
  rules:
    - path: /.*
      methods:
        - GET
        - POST
        - PUT
        - DELETE
      accessStrategies:
        - handler: no_auth
```

- Verify APIRule creation and status: `kubectl get apirules $NAME -n $NAMESPACE -o=jsonpath='{.status.APIRuleStatus.code}'`.
- Access the function's external address: `curl https://$NAME.$DOMAIN`.

These methods provide different ways to achieve the same result: exposing your Kyma function through an APIRule for external access. Remember to adjust the provided code snippets with your specific values.
