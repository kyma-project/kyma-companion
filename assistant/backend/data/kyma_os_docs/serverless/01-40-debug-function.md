# Debug a Function

This tutorial shows how to use an external IDE to debug a Function in Kyma CLI.

## Steps
Learn how to debug a Function with Visual Studio Code for Node.js or Python, or GoLand:

<!-- tabs:start -->

#### **Visual Studio Code**

1. In VSC, navigate to the location of the file with the Function definition.
2. Create the `.vscode` directory.
3. In the `.vscode` directory, create the `launch.json` file with the following content:

   For Node.js:
   ```json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "name": "attach",
         "type": "node",
         "request": "attach",
         "port": 9229,
         "address": "localhost",
         "localRoot": "${workspaceFolder}/kubeless",
         "remoteRoot": "/kubeless",
         "restart": true,
         "protocol": "inspector",
         "timeout": 1000
       }
     ]
   }
    ```
    For Python:
   ```json
   {
      "version": "0.2.0",
      "configurations": [
          {
              "name": "Python: Kyma function",
              "type": "python",
              "request": "attach",
              "pathMappings": [
                  {
                      "localRoot": "${workspaceFolder}",
                      "remoteRoot": "/kubeless"
                  }
              ],
              "connect": {
                  "host": "localhost",
                  "port": 5678
              }
          }
      ]
   }
    ```

4. Run the Function with the `--debug` flag.
    ```bash
    kyma run function --debug
    ```

#### **GoLand**

1. In GoLand, navigate to the location of the file with the Function definition.
2. Choose the **Add Configuration...** option.
3. Add new **Attach to Node.js/Chrome** configuration with these options:
    - Host: `localhost`
    - Port: `9229`
4. Run the Function with the `--debug` flag.
    ```bash
    kyma run function --debug
    ```

<!-- tabs:end -->