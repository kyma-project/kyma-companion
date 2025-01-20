# Expose a Function Using the APIRule Custom Resource - Steps
You can expose a Function using Kyma dashboard, Kyma CLI, or kubectl:
<!-- tabs:start -->
#### **Kyma Dashboard**
1. Select a namespace from the drop-down list in the top navigation panel. Make sure the namespace includes the Function that you want to expose using the APIRule CR.
2. Go to **Discovery and Network** > **API Rules**, and click on **Create API Rule**.
3. Enter the following information:
- The APIRule's **Name** matching the Function's name.
> [!NOTE]
> The APIRule CR can have a name different from that of the Function, but it is recommended that all related resources share a common name.
- **Service Name** matching the Function's name.
- **Host** to determine the host on which you want to expose your Function.
4. Edit the access strategy in the **Rules** > **Access Strategies** section
- Select the methods `GET`, `POST`, `PUT`, and `DELETE`.
- Use the default `no_auth` handler.
5. Select **Create** to confirm your changes.
6. Check if you can access the Function by selecting the HTTPS link under the **Host** column for the newly created APIRule. If successful, the `Hello World!` message appears.
#### **Kyma CLI**
1. Export these variables:
```bash
export DOMAIN={DOMAIN_NAME}
export NAME={FUNCTION_NAME}
export NAMESPACE={NAMESPACE_NAME}
```
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
- handler: no_auth
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
If successful, the `Hello World!` message appears.
#### **kubectl**
1. Export these variables:
```bash
export DOMAIN={DOMAIN_NAME}
export NAME={FUNCTION_NAME}
export NAMESPACE={FUNCTION_NAMESPACE}
```
> [!NOTE]
> The APIRule CR can have a name different from that of the Function, but it is recommended that all related resources share a common name.
2. Create an APIRule CR, which exposes your Function on port `80`.
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
If successful, the `Hello World!` message appears.
<!-- tabs:end -->