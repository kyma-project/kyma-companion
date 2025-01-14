# Changing Events Max-In-Flight in Subscriptions - Prerequisites
> [!NOTE]
> Read about the [Purpose and Benefits of Istio Sidecar Proxies](https://kyma-project.io/#/istio/user/00-00-istio-sidecar-proxies?id=purpose-and-benefits-of-istio-sidecar-proxies). Then, check how to [Enable Istio Sidecar Proxy Injection](https://kyma-project.io/#/istio/user/tutorials/01-40-enable-sidecar-injection). For more details, see [Default Istio Configuration](https://kyma-project.io/#/istio/user/00-15-overview-istio-setup) in Kyma.
1. Follow the [Prerequisites steps](evnt-01-prerequisites.md) for the Eventing tutorials.
2. [Create and Modify an Inline Function](https://kyma-project.io/#/serverless-manager/user/tutorials/01-10-create-inline-function).
3. For this tutorial, instead of the default code sample, replace the Function source with the following code. To simulate prolonged event processing, the Function waits for 5 seconds before returning the response.
<!-- tabs:start -->
#### **Kyma Dashboard**
```js
module.exports = {
main: async function (event, context) {
console.log("Processing event:", event.data);
// sleep/wait for 5 seconds
await new Promise(r => setTimeout(r, 5 * 1000));
console.log("Completely processed event:", event.data);
return;
}
}
```
#### **kubectl**
```bash
cat <<EOF | kubectl apply -f -
apiVersion: serverless.kyma-project.io/v1alpha2
kind: Function
metadata:
name: lastorder
namespace: default
spec:
replicas: 1
resourceConfiguration:
function:
profile: S
build:
profile: local-dev
runtime: nodejs18
source:
inline:
source: |-
module.exports = {
main: async function (event, context) {
console.log("Processing event:", event.data);
// sleep/wait for 5 seconds
await new Promise(r => setTimeout(r, 5 * 1000));
console.log("Completely processed event:", event.data);
return;
}
}
EOF
```
<!-- tabs:end -->