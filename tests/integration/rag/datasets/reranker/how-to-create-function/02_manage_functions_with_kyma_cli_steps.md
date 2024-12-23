# Manage Functions with Kyma CLI - Steps
Follow these steps:
1. To create local files with the default configuration for a Python Function, go to the folder in which you want to initiate the workspace content and run the `init` Kyma CLI command:
```bash
kyma init function --runtime python312 --name {FUNCTION_NAME}
```
You can also use the `--dir {FULL_FOLDER_PATH}` flag to point to the directory where you want to create the Function's source files.
> [!NOTE]
> Python 3.9 is only one of the available runtimes. Read about all [supported runtimes and sample Functions to run on them](../technical-reference/07-10-sample-functions.md).
The `init` command creates these files in your workspace folder:
- `config.yaml` with the Function's configuration
> [!NOTE]
> See the detailed description of all fields available in the [`config.yaml` file](../technical-reference/07-60-function-configuration-file.md).
- `handler.py` with the Function's code and the simple "Hello World" logic
- `requirements.txt` with an empty file for your Function's custom dependencies
The `kyma init` command also sets **sourcePath** in the `config.yaml` file to the full path of the workspace folder:
```yaml
name: my-function
namespace: default
runtime: python312
source:
sourceType: inline
sourcePath: {FULL_PATH_TO_WORKSPACE_FOLDER}
```
1. Run the `apply` Kyma CLI command to create a Function CR in the YAML format on your cluster:
```bash
kyma apply function
```
> [!TIP]
> To apply a Function from a different location, use the `--filename` flag followed by the full path to the `config.yaml` file.
Alternatively, use the `--dry-run` flag to list the file that will be created before you apply it. You can also preview the file's content in the format of your choice by adding the `--output {FILE_FORMAT}` flag, such as `--output yaml`.
3. Once applied, view the Function's details in the cluster:
```bash
kubectl describe function {FUNCTION_NAME}
```
4. Change the Function's source code in the cluster to return "Hello Serverless!":
a) Edit the Function:
```bash
kubectl edit function {FUNCTION_NAME}
```
b) Modify **source** as follows:
```yaml
...
spec:
runtime: python312
source: |-
def main(event, context):
return "Hello Serverless!"
```
5. Fetch the content of the resource to synchronize your local workspace sources with the cluster changes:
```bash
kyma sync function {FUNCTION_NAME}
```
6. Check the local `handler.py` file with the Function's code to make sure that the cluster changes were fetched:
```bash
cat handler.py
```
This command returns the result confirming that the local sources were synchronized with cluster changes:
```python
def main(event, context):
return "Hello Serverless!"
```