This Application uses an API-Rule. According to the [Troubleshooting Guide](https://github.com/kyma-project/api-gateway/blob/main/docs/user/troubleshooting-guides/03-40-api-rule-troubleshooting.md#unsupported-handlers-combination) a possible issue is to set a not-supported combination of access strategy handlers.

### Issue
Two conflicting handlers (`no_auth` and `allow`) are used, when only one is allowed at the same time.

```yaml
apiVersion: gateway.kyma-project.io/v1beta1
kind: APIRule
metadata:
  name: restapi
  namespace: kyma-app-broken-apirule
spec:
  host: kyma-app-broken-apirule.c-5cb6076.stage.kyma.ondemand.com
  service:
    name: restapi
    namespace: kyma-app-broken-apirule
    port: 80
  gateway: kyma-system/kyma-gatewa
  rules:
    - path: /.*
      methods: ["GET", "POST"]
      accessStrategies: # This should have only one handler:
        - handler: no_auth # this
        - handler: allow # OR this
```
