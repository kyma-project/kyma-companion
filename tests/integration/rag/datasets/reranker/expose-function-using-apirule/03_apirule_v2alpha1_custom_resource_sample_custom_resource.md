# APIRule v2alpha1 Custom Resource <!--  --> - Sample Custom Resource
See an exemplary APIRule custom resource:
```yaml
apiVersion: gateway.kyma-project.io/v2alpha1
kind: APIRule
metadata:
name: service-exposed
spec:
gateway: kyma-system/kyma-gateway
hosts:
- foo.bar
service:
name: foo-service
namespace: foo-namespace
port: 8080
timeout: 360
rules:
- path: /*
methods: [ "GET" ]
noAuth: true
```
This sample APIRule illustrates the usage of a short host name. It uses the domain from the referenced Gateway `kyma-system/kyma-gateway`:
```yaml
apiVersion: gateway.kyma-project.io/v2alpha1
kind: APIRule
metadata:
name: service-exposed
spec:
gateway: kyma-system/kyma-gateway
hosts:
- foo
service:
name: foo-service
namespace: foo-namespace
port: 8080
timeout: 360
rules:
- path: /*
methods: [ "GET" ]
noAuth: true
```