# APIRule v1beta1 Custom Resource <!--  --> - Sample Custom Resource
This is a sample custom resource (CR) that the APIGateway Controller listens for to expose a Service. The following
example has the **rules** section specified, which makes APIGateway Controller create an Oathkeeper Access Rule for the
Service.
```yaml
apiVersion: gateway.kyma-project.io/v1beta1
kind: APIRule
metadata:
name: service-secured
spec:
gateway: kyma-system/kyma-gateway
host: foo.bar
service:
name: foo-service
namespace: foo-namespace
port: 8080
timeout: 360
rules:
- path: /.*
methods: [ "GET" ]
mutators: [ ]
accessStrategies:
- handler: oauth2_introspection
config:
required_scope: [ "read" ]
```