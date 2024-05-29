# Forward a Client IP in the X-Forwarded-For Header

Many applications need to know the client IP address of an originating request to behave properly. Usual use cases include workloads that require the client IP address to restrict their access. The ability to provide client attributes to services has long been a staple of reverse proxies, which use the X-Forwarded-For (XFF) header to forward client attributes to destination workloads. For more information on XFF, see 
the [IETF’s RFC documentation](https://datatracker.ietf.org/doc/html/rfc7239) and [Envoy documentation](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_conn_man/headers#x-forwarded-for).

> [!NOTE]
>  The X-Forwarded-For header is only supported on AWS clusters.

## Prerequisites

* An AWS cluster
* The Istio module enabled or [Kyma Istio Operator](../../../../../README.md#install-kyma-istio-operator-and-istio-from-the-latest-release) installed
* [Istio Gateway](https://kyma-project.io/#/api-gateway/user/tutorials/01-20-set-up-tls-gateway) set up

## Steps

### Configure the Number of Trusted Proxies in the Istio Custom Resource

Applications rely on reverse proxies to forward the client IP address in a request using the XFF header. However, due to 
the variety of network topologies, you must specify the configuration property **numTrustedProxies**, so that the client address can be extracted correctly. This property indicates the number of trusted proxies deployed
in front of the Istio Gateway proxy.

Add **numTrustedProxies** to the Istio custom resource:

<!-- tabs:start -->
#### **kubectl**
Run the following command:

  ```bash
  kubectl patch istios/default -n kyma-system --type merge -p '{"spec":{"config":{"numTrustedProxies": 1}}}'
  ```

#### **Kyma Dashboard**
1. Navigate to `Cluster Details`.
2. Open the Istio module's configuration.
3. Click **Edit**.
4. Add the number of trusted proxies and click **Update**.
   ![Add the numTrustedProxies](./assets/01-00-num-trusted-proxies-ui.svg)
<!-- tabs:end -->


### Create a Workload for Verification

1. [Create an HttpBin workload](https://kyma-project.io/#/api-gateway/user/tutorials/01-00-create-workload).
2. Export the following values as environment variables.
    ```bash
    export DOMAIN_TO_EXPOSE_WORKLOADS={GATEWAY_DOMAIN}
    export GATEWAY={GATEWAY_NAMESPACE}/GATEWAY_NAME}
   ```
3. Expose the HttpBin workload using a VirtualService.
    ```bash
    cat <<EOF | kubectl apply -f -
    apiVersion: networking.istio.io/v1alpha3
    kind: VirtualService
    metadata:
      name: httpbin
      namespace: $NAMESPACE
    spec:
      hosts:
      - "httpbin.$DOMAIN_TO_EXPOSE_WORKLOADS"
      gateways:
      - $GATEWAY
      http:
      - match:
        - uri:
            prefix: /
        route:
        - destination:
            port:
              number: 8000
            host: httpbin.$NAMESPACE.svc.cluster.local
    EOF
    ```

### Verify the X-Forwarded-For and X-Envoy-External-Address Headers
1. Get your public IP address.
    ```bash
    curl -s https://api.ipify.org
    ```

2. Send a request to the HttpBin workload.
    ```bash
    curl -s "https://httpbin.$DOMAIN_TO_EXPOSE_WORKLOADS/get?show_env=true"
    ```
3. Verify that the response contains the **X-Forwarded-For** and **X-Envoy-External-Address** headers with your public IP address, for example:
    ```json
    {
      "args": {
        "show_env": "true"
      },
      "headers": {
        "Accept": "...",
        "Host": "...",
        "User-Agent": "...",
        "X-Envoy-Attempt-Count": "...",
        "X-Envoy-External-Address": "165.1.187.197",
        "X-Forwarded-Client-Cert": "...",
        "X-Forwarded-For": "165.1.187.197",
        "X-Forwarded-Proto": "...",
        "X-Request-Id": "..."
      },
      "origin": "165.1.187.197",
      "url": "..."
    }
    ``` 
