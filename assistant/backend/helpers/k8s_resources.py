import subprocess
import os

# The Python client API does not have an equivalent function to `kubectl api-resources`
# which is why the `kubectl` command is used here: https://stackoverflow.com/questions/76031802/
def extract_all_api_resources(env):
    return subprocess.check_output("""
                                   for i in $(kubectl api-resources --verbs=list -o name | grep -v "events.events.k8s.io" | grep -v "events" | sort | uniq); do
                                   echo $i
                                   done
                                   """, shell=True, text=True, env=env).split("\n")


def extract_namespace_scoped_resources(env):
    return subprocess.check_output("""
                                   for i in $(kubectl api-resources --namespaced --verbs=list -o name | grep -v "events.events.k8s.io" | grep -v "events" | sort | uniq); do
                                   echo $i
                                   done
                                   """, shell=True, text=True, env=env).split("\n")


def extract_resource_names(resourceType, namespace, env):
    if namespace:
        return subprocess.check_output(f"""
                                       for i in $(kubectl get -n {namespace} {resourceType} -o=jsonpath='{{range .items[*]}}{{.metadata.name}}\n{{end}}'); do
                                       echo $i
                                       done
                                       """, shell=True, text=True, env=env).split("\n")
    else:
        return subprocess.check_output(f"""
                                       for i in $(kubectl get {resourceType} -o=jsonpath='{{range .items[*]}}{{.metadata.name}}\n{{end}}'); do
                                       echo $i
                                       done
                                       """, shell=True, text=True, env=env).split("\n")

def extract_kubernetes_resources(command: str) -> str:
    kube_env = os.environ.copy()
    resource = ""
    try:
        # Run the kubectl command and capture the output
        resource = subprocess.check_output(command, shell=True, text=True, env=kube_env)
    except subprocess.CalledProcessError as e:
        # If the command returns a non-zero status, capture the error output
        error_output = e.output
        print(f"Error: {error_output}")
    return resource
