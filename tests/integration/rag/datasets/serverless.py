from textwrap import dedent

cases = [
    {
        "input": "How to expose a Function Using the APIRule Custom Resource?",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
            To expose a Kyma function using the APIRule custom resource, you have three options:

            **1. Kyma Dashboard:**

            - Navigate to **Discovery and Network** > **API Rules** and click **Create API Rule**.
            - Provide the APIRule name (matching the function's name is recommended), service name, and desired host.
            - In **Rules** > **Access Strategies**, select methods (GET, POST, PUT, DELETE) and the `no_auth` handler for an unsecured endpoint.
            - Click **Create** and test the exposed function using the HTTPS link under the **Host** column.


            **2. Kyma CLI:**

            - Export `DOMAIN`, `NAME` (function name), and `NAMESPACE`.
            - Download the function's configuration: `kyma sync function $NAME -n $NAMESPACE`.
            - Edit `config.yaml` to include the `apiRules` schema:

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

            - Apply the configuration: `kyma apply function`.
            - Verify the APIRule creation and status: `kubectl get apirules $NAME -n $NAMESPACE` and `kubectl get apirules $NAME -n $NAMESPACE -o=jsonpath='{.status.APIRuleStatus.code}'`.
            - Call the function's external address: `curl https://$NAME.$DOMAIN`.


            **3. kubectl:**

            - Export `DOMAIN`, `NAME`, and `NAMESPACE`.
            - Create an APIRule CR using `kubectl apply -f -` with the following YAML structure:

            ```yaml
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
            ```

            - Verify APIRule creation and status: `kubectl get apirules $NAME -n $NAMESPACE -o=jsonpath='{.status.APIRuleStatus.code}'`.
            - Access the function's external address: `curl https://$NAME.$DOMAIN`.

            These methods provide different ways to achieve the same result: exposing your Kyma function through an APIRule for external access. Remember to adjust the provided code snippets with your specific values.
            """
        ),
    },
    {
        "input": "How to create a Function?",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
            # Create and Modify an Inline Function

            This tutorial shows how you can create a simple "Hello World" Function in Node.js. The Function's code and dependencies are defined as an inline code in the Function's **spec**.

            Serverless also allows you to store the Function's code and dependencies as sources in a Git repository. To learn more, read how to [Create a Git Function](01-11-create-git-function.md).
            To learn more about Function's signature, `event` and `context` objects, and custom HTTP responses the Function returns, read [Function’s specification](../technical-reference/07-70-function-specification.md).

            > [!NOTE]
            > Read about [Istio sidecars in Kyma and why you want them](https://kyma-project.io/docs/kyma/latest/01-overview/service-mesh/smsh-03-istio-sidecars-in-kyma/). Then, check how to [enable automatic Istio sidecar proxy injection](https://kyma-project.io/docs/kyma/latest/04-operation-guides/operations/smsh-01-istio-enable-sidecar-injection/). For more details, see [Default Istio setup in Kyma](https://kyma-project.io/docs/kyma/latest/01-overview/service-mesh/smsh-02-default-istio-setup-in-kyma/).

            ## Steps

            You can create a Function with Kyma dashboard, Kyma CLI, or kubectl:

            <!-- tabs:start -->

            #### **Kyma Dashboard**

            > [!NOTE]
            > Kyma dashboard uses Busola, which is not installed by default. Follow the [installation instructions](https://github.com/kyma-project/busola/blob/main/docs/install-kyma-dashboard-manually.md).

            1. Create a namespace or select one from the drop-down list in the top navigation panel.

            2. Go to **Workloads** > **Functions** and select **Create Function**.

            3. In the dialog box, provide the Function's name or click on **Generate**.

            > [!NOTE]
            > The **Node.js Function** preset is selected by default. It means that the selected runtime is `Node.js`, and the **Source** code is autogenerated. You can choose the Python runtime by clicking on the **Choose preset** button.

              ```js
              module.exports = {
                main: async function (event, context) {
                  const message =
                    `Hello World` +
                    ` from the Kyma Function ${context['function-name']}` +
                    ` running on ${context.runtime}!`;
                  console.log(message);
                  return message;
                },
              };
              ```

            The dialog box closes. Wait for the **Status** field to change into `RUNNING`, confirming that the Function was created successfully.

            1. If you decide to modify it, click **Edit** and confirm changes afterward by selecting the **Update** button. You will see the message at the bottom of the screen confirming the Function was updated.

            #### **Kyma CLI**

            1. Export these variables:

                ```bash
                export NAME={FUNCTION_NAME}
                export NAMESPACE={FUNCTION_NAMESPACE}
                ```

            2. Create your local development workspace.

                a. Create a new folder to keep the Function's code and configuration in one place:

                ```bash
                mkdir {FOLDER_NAME}
                cd {FOLDER_NAME}
                ```

                b. Create initial scaffolding for the Function:

                ```bash
                kyma init function --name $NAME --namespace $NAMESPACE
                ```

            3. Code and configure.

                Open the workspace in your favorite IDE. If you have Visual Studio Code installed, run the following command from the terminal in your workspace folder:

                ```bash
                code .
                ```

                It's time to inspect the code and the `config.yaml` file. Feel free to adjust the "Hello World" sample code.

            4. Deploy and verify.

                a. Call the `apply` command from the workspace folder. It will build the container and run it on the Kyma runtime pointed by your current KUBECONFIG file:

                  ```bash
                  kyma apply function
                  ```

                b. Check if your Function was created successfully:

                  ```bash
                  kubectl get functions $NAME -n $NAMESPACE
                  ```

                You should get a result similar to this example:

                ```bash
                NAME            CONFIGURED   BUILT     RUNNING   RUNTIME    VERSION   AGE
                test-function   True         True      True      nodejs20   1         96s
                ```

            #### **kubectl**

            1. Export these variables:

                ```bash
                export NAME={FUNCTION_NAME}
                export NAMESPACE={FUNCTION_NAMESPACE}
                ```

            2. Create a Function CR that specifies the Function's logic:

              ```bash
              cat <<EOF | kubectl apply -f -
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
              EOF
              ```

            3. Check if your Function was created successfully and all conditions are set to `True`:

                ```bash
                kubectl get functions $NAME -n $NAMESPACE
                ```

                You should get a result similar to this example:

                ```bash
                NAME            CONFIGURED   BUILT     RUNNING   RUNTIME    VERSION   AGE
                test-function   True         True      True      nodejs20   1         96s
                ```

            <!-- tabs:end -->
            """
        ),
    },
    {
        "input": "How to create custom tracing spans for a function?",
        "answer_relevancy_threshold": 0.6,
        "expected_output": dedent(
            """
            Kyma Functions are automatically instrumented to handle trace headers, so every time you call your function, the executed logic is traceable. You can further customize this by creating your own custom spans, adding events, and tags to the tracing context.

            Here's how you can create a tracing span for a Kyma function:

            **1. Prerequisites:**

            * Ensure you have the Telemetry component installed in your Kyma environment.
            * Configure a trace pipeline to visualize and analyze your traces.

            **2. Code Example (Node.js):**

            ```javascript
            const { SpanStatusCode } = require("@opentelemetry/api/build/src/trace/status");
            const axios = require("axios")
            module.exports = {
              main: async function (event, context) {

                  const data = {
                    name: "John",
                    surname: "Doe",
                    type: "Employee",
                    id: "1234-5678"
                  }

                  const span = event.tracer.startSpan('call-to-acme-service');
                  return await callAcme(data)
                    .then(resp => {
                        if(resp.status!==200){
                          throw new Error("Unexpected response from acme service");
                        }
                        span.addEvent("Data sent");
                        span.setAttribute("data-type", data.type);
                        span.setAttribute("data-id", data.id);
                        span.setStatus({code: SpanStatusCode.OK});
                        return "Data sent";
                    }).catch(err=> {
                        console.error(err)
                        span.setStatus({
                          code: SpanStatusCode.ERROR,
                          message: err.message,
                        });
                        return err.message;
                    }).finally(()=>{
                        span.end();
                    });
              }
            }

            let callAcme = (data)=>{
              return axios.post('https://acme.com/api/people', data)
            }
            ```

            **Explanation:**

            * This code snippet demonstrates creating a custom span named `call-to-acme-service` using `event.tracer.startSpan()`.
            * Inside the span, you can add events (`span.addEvent()`), attributes (`span.setAttribute()`), and set the status (`span.setStatus()`).
            * Finally, remember to end the span using `span.end()` when the operation is complete.

            **3. Visualizing Traces:**

            Once you have your function set up and deployed, you can visualize the traces in your configured trace backend. You should see the custom span you created along with the default function execution span, providing detailed insights into the function's performance and behavior.

            **Additional Tips:**

            * You can create nested spans to track hierarchical operations within your function.
            * Use attributes to add contextual information to your spans, such as user IDs, request parameters, or error codes.
            * Leverage events to capture specific points of interest within the span's timeline.

            By effectively utilizing custom spans, events, and attributes, you can gain a deeper understanding of your Kyma functions' execution flow and performance characteristics.

            """
        ),
    },
    {
        "input": "How to add a new environment variable to a function?",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
            # Inject Environment Variables

            This tutorial shows how to inject environment variables into Function.

            You can specify environment variables in the Function definition, or define references to the Kubernetes Secrets or ConfigMaps.

            ## Prerequisites

            Before you start, make sure you have these tools installed:

            - [Serverless module installed](https://kyma-project.io/docs/kyma/latest/04-operation-guides/operations/08-install-uninstall-upgrade-kyma-module/) in a cluster

            ## Steps

            Follow these steps:

            1. Create your ConfigMap

            ```bash
            kubectl create configmap my-config --from-literal config-env="I come from config map"
            ```

            2. Create your Secret

            ```bash
            kubectl create secret generic my-secret --from-literal secret-env="I come from secret"
            ```

            <!-- tabs:start -->

            #### **Kyma CLI**

            3. Generate the Function's configuration and sources:

                ```bash
                kyma init function --name my-function
                ```

            4. Define environment variables as part of the Function configuration file. Modify `config.yaml` with the following:

                ```yaml
                name: my-function
                namespace: default
                runtime: nodejs20
                source:
                    sourceType: inline
                env:
                  - name: env1
                    value: "I come from function definition"
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

            5. Use injected environment variables in the handler file. Modify `handler.js` with the following:

                ```js
                module.exports = {
                    main: function (event, context) {
                        envs = ["env1", "env2", "env3"]
                        envs.forEach(function(key){
                            console.log(`${key}:${readEnv(key)}`)
                        });
                        return 'Hello Serverless'
                    }
                }

                readEnv=(envKey) => {
                    if(envKey){
                        return process.env[envKey];
                    }
                    return
                }
                ```

            6. Deploy your Function:

                ```bash
                kyma apply function
                ```

            7. Verify whether your Function is running:

                ```bash
                kubectl get functions my-function
                ```

            #### **kubectl**

            3. Create a Function CR that specifies the Function's logic:

              ```bash
              cat <<EOF | kubectl apply -f -
              apiVersion: serverless.kyma-project.io/v1alpha2
              kind: Function
              metadata:
                name: my-function
              spec:
                env:
                  - name: env1
                    value: I come from function definition
                  - name: env2
                    valueFrom:
                      configMapKeyRef:
                        key: config-env
                        name: my-config
                  - name: env3
                    valueFrom:
                      secretKeyRef:
                        key: secret-env
                        name: my-secret
                runtime: nodejs20
                source:
                  inline:
                    source: |-
                      module.exports = {
                          main: function (event, context) {
                              envs = ["env1", "env2", "env3"]
                              envs.forEach(function(key){
                                  console.log(\`${key}:${readEnv(key)}\`)
                              });
                              return 'Hello Serverless'
                          }
                      }
                      readEnv=(envKey) => {
                          if(envKey){
                              return process.env[envKey];
                          }
                          return
                      }
              EOF
              ```

            4. Verify whether your Function is running:

                ```bash
                kubectl get functions my-function
                ```

            <!-- tabs:end -->
            """
        ),
    },
    {
        "input": "Why does a serverless function pod have many restarts?",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
            If your serverless function pod has lots of restarts, it might be due to the Function Controller crashing and restarting. This can happen when you have many Git-sourced Functions deployed together that reference large repositories. The periodic polling for changes in these repositories can cause high demand on CPU and I/O resources, leading to the Function Controller crashing.

            To avoid this, try to use small, dedicated repositories for your Git Functions. This will reduce the resource usage and improve the stability of the Function Controller.
            """
        ),
    },
]
