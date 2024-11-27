To create a Kyma function, you have three options:

**1. Kyma Dashboard:**

- Ensure you have the Kyma Dashboard (Busola) installed.
- Select a namespace.
- Go to **Workloads** > **Functions** > **Create Function**.
- Provide a name or generate one.
- The Node.js preset is selected by default, providing a basic "Hello World" function. You can switch to Python if needed.
- Wait for the status to change to `RUNNING`.
- Edit the function's code using the **Edit** button if needed.

**2. Kyma CLI:**

- Export `NAME` and `NAMESPACE`.
- Create a folder: `mkdir {FOLDER_NAME}` and `cd {FOLDER_NAME}`.
- Initialize the function: `kyma init function --name $NAME --namespace $NAMESPACE`.
- Edit the generated code and `config.yaml` in your IDE.
- Apply the function: `kyma apply function`.
- Verify creation: `kubectl get functions $NAME -n $NAMESPACE`.

**3. kubectl:**

- Export `NAME` and `NAMESPACE`.
- Create a Function CR using `kubectl apply -f -` with the following structure:

```yaml
apiVersion: serverless.kyma-project.io/v1alpha2
kind: Function
metadata:
  name: $NAME
  namespace: $NAMESPACE
spec:
  runtime: nodejs20
  source:
    inline:
      source: |
        module.exports = {
          main: function(event, context) {
            return 'Hello World!'
          }
        }
```

- Verify creation and status: `kubectl get functions $NAME -n $NAMESPACE`.

These methods offer different ways to create your Kyma function, providing flexibility based on your preference and workflow.
