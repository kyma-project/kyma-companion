# Use an External Authorization Provider to Expose and Secure a Workload

This tutorial shows how to expose and secure an HTTPBin Service using an external authorization provider.

## Prerequisites

* Kyma installation with the Istio module enabled. If you use a Kyma domain, also the API Gateway module must be enabled.
* Prepare a domain you want to use and export its name as an environment variable:
    ```
    export DOMAIN_TO_EXPOSE_WORKLOADS={DOMAIN_NAME}
    ```
* Depending on whether you use your custom domain or a Kyma domain, export the necessary values as environment variables:

    <!-- tabs:start -->
    #### **Custom Domain**

    ```bash
    export DOMAIN_TO_EXPOSE_WORKLOADS={DOMAIN_NAME}
    export GATEWAY=$NAMESPACE/httpbin-gateway
    ```
    #### **Kyma Domain**

    ```bash
    export DOMAIN_TO_EXPOSE_WORKLOADS={KYMA_DOMAIN_NAME}
    export GATEWAY=kyma-system/kyma-gateway
    ```
    <!-- tabs:end -->

## Steps

### Create a Workload

1. Export the name of the namespace in which you want to deploy the HTTPBin Service:

    ```
    export NAMESPACE={NAMESPACE_NAME}
    ```

2. Create a namespace with Istio injection enabled and deploy the HTTPBin Service:

    ```
    kubectl create ns $NAMESPACE
    kubectl label namespace $NAMESPACE istio-injection=enabled --overwrite
    kubectl create -n $NAMESPACE -f https://raw.githubusercontent.com/istio/istio/master/samples/httpbin/httpbin.yaml
    ```

### Expose an HTTPBin Service

Create a VirtualService to expose the HTTPBin workload.

```
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
          number: 80
        host: httpbin.$NAMESPACE.svc.cluster.local
EOF
```

### Install and Configure oauth2-proxy

To learn more about oauth2-proxy, [see the documentation](https://github.com/oauth2-proxy/manifests/tree/main/helm/oauth2-proxy).

1. Export your configuration values as environment variables:
    ```
    export CLIENT_ID={CLIENT_ID}
    export CLIENT_SECRET={CLIENT_SECRET}
    export COOKIE_SECRET={COOKIE_SECRET}
    export OIDC_ISSUER_URL={OIDC_ISSUER_URL}
    ```

2. Create a `values.yaml` file with the configuration of oauth2-proxy:
    ```
    cat <<EOF > values.yaml
    config:
      clientID: $CLIENT_ID
      clientSecret: $CLIENT_SECRET
      cookieSecret: $COOKIE_SECRET
    extraArgs:
      provider: oidc
      cookie-secure: false
      cookie-domain: "$DOMAIN_TO_EXPOSE_WORKLOADS"
      cookie-samesite: lax
      set-xauthrequest: true
      whitelist-domain: "*.$DOMAIN_TO_EXPOSE_WORKLOADS:*"
      reverse-proxy: true
      pass-access-token: true 
      set-authorization-header: true
      pass-authorization-header: true
      scope: "openid email"
      upstream: static://200
      skip-provider-button: true
      redirect-url: "https://oauth2-proxy.$DOMAIN_TO_EXPOSE_WORKLOADS/oauth2/callback"
      oidc-issuer-url: https://$OIDC_ISSUER_URL
      code-challenge-method: S256
    EOF
    ```

3. Install oauth2-proxy with your configuration using Helm:
    ```
    helm repo add oauth2-proxy https://oauth2-proxy.github.io/manifests
    helm install custom oauth2-proxy/oauth2-proxy -f values.yaml
    ```

### Configure Istio Custom Resource (CR) with an External Authorization Provider

1. Apply Istio CR configuration with an external authorization provider. Here's an example configuration:
    ```
    cat <<EOF | kubectl apply -f -
    apiVersion: operator.kyma-project.io/v1alpha1
    kind: Istio
    metadata:
      name: default
      namespace: kyma-system
    spec:
      config:
        numTrustedProxies: 1
        authorizers:
        - name: "oauth2-proxy"
          service: "custom-oauth2-proxy.$NAMESPACE.svc.cluster.local"
          port: 80
          headers:
            inCheck:
              include: ["authorization", "cookie"]
              add:
                x-auth-request-redirect: "https://%REQ(:authority)%%REQ(x-envoy-original-path?:path)%"
            toUpstream:
              onAllow: ["authorization", "path", "x-auth-request-user", "x-auth-request-email", "x-auth-request-access-token"]
            toDownstream:
              onAllow: ["set-cookie"]
              onDeny: ["content-type", "set-cookie"]
    EOF
    ```

2. Create an AuthorizationPolicy CR with the `CUSTOM` action and the `oauth2-proxy` provider:
    ```
    cat <<EOF | kubectl apply -f -
    apiVersion: security.istio.io/v1
    kind: AuthorizationPolicy
    metadata:
        name: ext-authz
        namespace: test
    spec:
      action: CUSTOM
      provider:
        name: oauth2-proxy
      rules:
      - to:
        - operation:
            paths:
            - /headers
      selector:
        matchLabels:
          app: httpbin
    EOF
    ```

3. Create a DestinationRule with a traffic policy for the external authorization provider:
    ```
    cat <<EOF | kubectl apply -f -
    apiVersion: networking.istio.io/v1beta1
    kind: DestinationRule
    metadata:
      name: external-authz-https
      namespace: istio-system
    spec:
      host: $OIDC_ISSUER_URL
      trafficPolicy:
        tls:
          mode: SIMPLE
    EOF
    ```

4. To test the configuration, visit the `https://httpbin.$DOMAIN_TO_EXPOSE_WORKLOADS/headers` URL. You should be redirected to the authorization provider.
