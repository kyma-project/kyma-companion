To inject environment variables into a Kyma function, you can define them directly in the Function definition, or reference existing Kubernetes Secrets and ConfigMaps. Here's how:

**1. Define in Function Definition:**

   * **Using Kyma CLI:**
      - Generate function: `kyma init function --name my-function`
      - Edit `config.yaml`:
        ```yaml
        env:
          - name: env1
            value: "I come from function definition" 
        ```
      - Apply function: `kyma apply function`

   * **Using kubectl:**
      - Create Function CR:
        ```yaml
        apiVersion: serverless.kyma-project.io/v1alpha2
        kind: Function
        metadata:
          name: my-function
        spec:
          env:
            - name: env1
              value: I come from function definition
          ... 
        ```
      - Apply: `kubectl apply -f -`


**2. Reference Secrets and ConfigMaps:**

   - **Create ConfigMap:**
     ```bash
     kubectl create configmap my-config --from-literal config-env="I come from config map"
     ```

   - **Create Secret:**
     ```bash
     kubectl create secret generic my-secret --from-literal secret-env="I come from secret"
     ```

   - **Reference in Function definition:**
     ```yaml
     env:
       - name: env2
         valueFrom:
           configMapKeyRef:
             name: my-config
             key: config-env
       - name: env3
         valueFrom:
           secretKeyRef:
             name: my-secret
             key: secret-env
     ```

**3. Access in your Function Code:**

   - Access environment variables in your function code using `process.env`:

     ```javascript
     module.exports = {
         main: function (event, context) {
             console.log(process.env.env1); // Access env1
             console.log(process.env.env2); // Access env2
             console.log(process.env.env3); // Access env3
             return 'Hello Serverless'
         }
     }
     ```

By following these steps, you can effectively inject environment variables into your Kyma functions, either directly or by referencing Kubernetes resources.
