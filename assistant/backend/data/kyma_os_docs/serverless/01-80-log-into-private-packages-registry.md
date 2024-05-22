# Log Into a Private Package Registry Using Credentials from a Secret

Serverless allows you to consume private packages in your Functions. This tutorial shows how you can log into a private package registry by defining credentials in a Secret custom resource (CR).

## Steps

### Create a Secret

Create a Secret CR for your Node.js or Python Functions. You can also create one combined Secret CR for both runtimes.

<!-- tabs:start -->

#### **Node.js**

1. Export these variables:

 ```bash
 export REGISTRY={ADDRESS_TO_REGISTRY}
 export TOKEN={TOKEN_TO_REGISTRY}
 export NAMESPACE={FUNCTION_NAMESPACE}
 ```

2. Create a Secret:

 ```bash
 cat <<EOF | kubectl apply -f -
 apiVersion: v1
 kind: Secret
 metadata:
   name: serverless-package-registry-config
   namespace: {NAMESPACE}
 type: Opaque
 stringData:
   .npmrc: |
       registry=https://{REGISTRY}
       //{REGISTRY}:_authToken={TOKEN}
EOF
 ```

#### **Python**

1. Export these variables:

 ```bash
 export REGISTRY={ADDRESS_TO_REGISTRY}
 export NAMESPACE={FUNCTION_NAMESPACE}
 export USERNAME={USERNAME_TO_REGISTRY}
 export PASSWORD={PASSWORD_TO_REGISTRY}
 ```

2. Create a Secret:

 ```bash
 cat <<EOF | kubectl apply -f -
 apiVersion: v1
 kind: Secret
 metadata:
   name: serverless-package-registry-config
   namespace: {NAMESPACE}
 type: Opaque
 stringData:
   pip.conf: |
     [global]
     extra-index-url = {USERNAME}:{PASSWORD}@{REGISTRY}
EOF
 ```

#### **Node.js & Python**

1. Export these variables:

 ```bash
 export REGISTRY={ADDRESS_TO_REGISTRY}
 export TOKEN={TOKEN_TO_REGISTRY}
 export NAMESPACE={FUNCTION_NAMESPACE}
 export USERNAME={USERNAME_TO_REGISTRY}
 export PASSWORD={PASSWORD_TO_REGISTRY}
 ```

2. Create a Secret:

 ```bash
 cat <<EOF | kubectl apply -f -
 apiVersion: v1
 kind: Secret
 metadata:
   name: serverless-package-registry-config
   namespace: {NAMESPACE}
 type: Opaque
 stringData:
   .npmrc: |
       registry=https://{REGISTRY}
       //{REGISTRY}:_authToken={TOKEN}
   pip.conf: |
       [global]
       extra-index-url = {USERNAME}:{PASSWORD}@{REGISTRY}
EOF
 ```

<!-- tabs:end -->

### Test the Package Registry Switch

[Create a Function](01-10-create-inline-function.md) with dependencies from the external registry. Check if your Function was created and all conditions are set to `True`:

```bash
kubectl get functions -n $NAMESPACE
```

You should get a result similar to the this example:

```bash
NAME            CONFIGURED   BUILT     RUNNING   RUNTIME    VERSION   AGE
test-function   True         True      True      nodejs20   1         96s
```

> [!WARNING]
> If you want to create a cluster-wide Secret, you must create it in the `kyma-system` namespace and add the `serverless.kyma-project.io/config: credentials` label.
