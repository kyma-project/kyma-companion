# Set Up and Run the Release Testing GitHub Action

This document provides a step-by-step guide to setting up and running the release testing GitHub Action for your backend's end-to-end (E2E) testing. Follow these steps to ensure your CI/CD pipeline is correctly configured and executed.

## Overview

The GitHub Action is triggered on pull requests (PRs) to the `main` branch within the `assistant/backend` directory. The workflow:
* Sets up a local Docker image registry
* Builds and pushes a Docker image
* Configures and installs a K3s cluster
* Deploys the image to the cluster
* Performs health checks and resource tests

## Files and Folders
<!--what is this list?-->
* GitHub Action Workflow: `.github/workflows`
* Backend code: `assistant/backend`
* Kubernetes related scripts and deployment files: `.scripts/kubernetes`
* Shell scripts (k3s installation, deployment verification, test scripts): `.scripts/shell`

## Secrets
<!--what is this list?-->
* Secret for Backend (K3S_SECRET) <!--is this a variable?-->
* ConfigMap for Backend (K3S_CONFIGMAP)
* User for `sap-llm-commons` (JFROG_IDENTITY_USER)
* Token for `sap-llm-commons` (JFROG_IDENTITY_TOKEN)
* GitHub PAT user for container registry (GH_CR_USER) - requires <!--required? or who requires?--> for the release process
* GitHub PAT token for container registry (GH_CR_PAT) - requires <!--required? or who requires?--> for the release process


## Release Testing Workflow Steps

![Release Testing Workflow Steps](../images/release-testing-workflow-steps.drawio.svg)

### Workflow Trigger

The workflow is triggered by:

* Push events to the `main` branch.
* Pull request events targeting the `main` branch.

The paths filter ensures that only changes within the `assistant/backend` directory trigger the workflow.

```yaml
on:
  pull_request_target:
    branches:
      - main
    paths:
      - "assistant/backend/**"
```

`pull_request_target` is used to run the workflow on the base branch of the PR. This allows for accessing the base branch's secrets and environment variables.

### Environment Variables

A Docker timeout environment variable is set to 30 seconds.

```yaml
env:
  DOCKER_TIMEOUT: 30
```

### Job Configuration

The job `build` is configured to run on the latest Ubuntu environment with write permissions.

```yaml
jobs:
  build:
    name: Backend E2E test
    runs-on: ubuntu-latest
    permissions: write-all
    steps:
```

### Steps in the Job

The `.github/workflows/backend-e2e-test.yaml` job performs the following actions:

1. Check out the code from the repository. (PR version)

    ```yaml
    - name: Prep - Checkout code
      uses: actions/checkout@v4
      with:
        ref: ${{ github.event.pull_request.head.ref }}
        repository: ${{ github.event.pull_request.head.repo.full_name }}
    ```

2. Create a local Docker image registry.

    ```yaml
    - name: Prep - Local Image registry
      run: |
        docker run -d -p 5000:5000 --restart=always --name registry registry:2
    ```

3. Build the local Docker image using the provided JFrog credentials.

    ```yaml
    - name: Build - Docker image
      working-directory: ./assistant/backend
      run: |
        docker build --build-arg "JFROG_USER=${{ secrets.JFROG_IDENTITY_USER }}" --build-arg "JFROG_TOKEN=${{ secrets.JFROG_IDENTITY_TOKEN }}" -t ai-backend .
    ```

4. Check the Docker image.
   
    ```yaml
    - name: Build - Check Docker image
      run: docker images ai-backend
    ```
    
5. Tag and push the Docker image to the local registry. Verify the Docker image creation.

    ```yaml
    - name: Publish - Push image to local registry
      run: |
        docker tag ai-backend:latest localhost:5000/ai-backend:latest
        docker push localhost:5000/ai-backend:latest
    ```

6. Configure K3s for the local Docker image registry. 

    ```yaml
    - name: K3s - Configure local registry for k3s
      run: |
        mkdir -p ~/.k3s
        cp .scripts/kubernetes/registries.yaml ~/.k3s/registries.yaml
    ```

7. Install and configure the K3s cluster using a shell script.

    ```yaml
    - name: K3s - Install and configure K3s cluster
      run: .scripts/shell/k3s-installation.sh
    ```
   
8. Verify the K3s cluster by checking Nodes and namespaces.
   
    ```yaml
    - name: K3s - Verify K3s cluster
      run: |
        kubectl get nodes
        kubectl get ns
    ```

9.  Deploy: Create the namespace for the deployment.

    ```yaml
    - name: Deploy - Create namespace
      run: |
        kubectl apply -f .scripts/kubernetes/ai-backend-namespace.yaml
    ```

10. Deploy: Create a Secret in the K3s cluster.

    ```yaml
    - name: Deploy - Create secret on K3s
      run: |
        echo "${{ secrets.K3S_SECRET }}" > .scripts/kubernetes/ai-backend-secret.yaml
        kubectl apply -f .scripts/kubernetes/ai-backend-secret.yaml
        rm -f .scripts/kubernetes/ai-backend-secret.yaml
    ```

11. Deploy: Create a ConfigMap in the K3s cluster.

    ```yaml
    - name: Deploy - Create configmap on K3s
      run: |
        echo "${{ secrets.K3S_CONFIGMAP }}" > .scripts/kubernetes/ai-backend-configmap.yaml
        kubectl apply -f .scripts/kubernetes/ai-backend-configmap.yaml
        rm -f .scripts/kubernetes/ai-backend-configmap.yaml
    ```

12. Deploy the Docker image and create a NodePort service.

    ```yaml
    - name: Deploy - Create Backend and NodePort service
      run: |
        kubectl apply -f .scripts/kubernetes/ai-backend-deployment.yaml
    ```

13. Deploy: Wait for the deployment to complete using a shell script.

    ```yaml
    - name: Deploy - Wait for deployment
      run: .scripts/shell/deploy-wait-for-deployment.sh $DOCKER_TIMEOUT
    ```

14. Test: Perform a health check on the backend.

    ```yaml
    - name: Test - Health check
      run: .scripts/shell/test-health-check.sh
    ```

15. Test: Check the resources in the cluster.

    ```yaml
    - name: Test - Cluster resources
      run: .scripts/shell/test-api-v1-resources.sh
    ```


## Conclusion

This document outlines the steps to set up and run the release testing GitHub Action for your backend service. Ensure that all the required scripts and secrets are properly configured in your repository for the workflow to execute successfully. If you encounter any issues, review the logs for each step to identify and resolve errors.