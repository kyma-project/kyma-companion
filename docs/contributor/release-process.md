# Backend - Release Workflow

This document provides a step-by-step guide to the release process workflow for building and pushing a Go project using GitHub Actions. This workflow is triggered on pushes to the `main` branch and tags, specifically for changes within the `assistant/backend` directory.

## Prerequisites

A pull request (PR) to the `main` branch must:
  * Have the `lgtm` label
  * Get approval from at least one reviewer <!--code owner?-->
  * Pass all checks (Bckend E2E tests, Linting, Git Leaks)

## Files and Folders
<!--what is this list?-->
- GitHub Action Workflow: `.github/workflows`
- Backend code: `assistant/backend`
- Kubernetes related scripts and deployment files: `.scripts/kubernetes`
- Shell scripts (k3s installation, deployment verification, test scripts): `.scripts/shell`

## Secrets
<!--what is this list?-->
- User for `sap-llm-commons` (JFROG_IDENTITY_USER)
- Token for `sap-llm-commons` (JFROG_IDENTITY_TOKEN)
- GitHub PAT user for container registry (GH_CR_USER) - requires <!--required? or who requires?--> for the release process
- GitHub PAT token for container registry (GH_CR_PAT) - requires <!--required? or who requires?--> for the release process

## Workflow Overview

The workflow performs the following key steps:

* Triggers the workflow on push events to the `main` branch and tags.
* Sets up environment variables.
* Checks out the code from the repository.
* Logs in to the Docker registry.
* Extracts Docker metadata.
* Builds and pushes the Docker image.

## Release Process Workflow Details

![Release Process Workflow Steps](../images/release-process-workflow-steps.drawio.svg)

### Workflow Trigger

The workflow is triggered by:

* Push events to the `main` branch.
* Tags matching the pattern `*.*.*`.
* Changes within the `assistant/backend` directory.

```yaml
on:
  push:
    branches: ["main"]
    tags: ["*.*.*"]
    paths:
      - "assistant/backend/**"
```

### Environment Variables

Define the following environment variables:

**IMAGE_REGISTRY**: The Docker image registry (for example, `ghcr.io`).
**ORGANIZATION**: The organization name (for example, `kyma-project`).
**REPOSITORY_NAME**: The repository name (for example, `kyma-companion`).
**IMAGE_NAME**: The Docker image name (for example, `ai-backend`).

```yaml
env:
  IMAGE_REGISTRY: ghcr.io
  ORGANIZATION: kyma-project
  REPOSITORY_NAME: kyma-companion
  IMAGE_NAME: ai-backend
```

### Job Configuration

The job build runs on the latest Ubuntu environment with write permissions.

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    permissions: write-all
    steps:
```

### Steps in the Job

1. Check out the code from the repository.

    ```yaml
    - name: Checkout code
      uses: actions/checkout@v4
    ```

1. Log into the Docker registry using the provided credentials.

    ```yaml
    - name: Log into registry ${{ env.IMAGE_REGISTRY }}
      uses: docker/login-action@v3
      with:
        registry: ${{ env.IMAGE_REGISTRY }}
        username: ${{ secrets.GH_CR_USER }}
        password: ${{ secrets.GH_CR_PAT }}
    ```

1. Extract metadata for the Docker image, including tags and labels.

    ```yaml
    - name: Extract Docker metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.IMAGE_REGISTRY }}/${{ env.ORGANIZATION }}/${{ env.REPOSITORY_NAME }}/${{ env.IMAGE_NAME }}
        tags: |
          type=sha
          type=raw,value=latest,event=push
          type=semver,pattern={{version}},event=tag
    ```

1. Build and push the Docker image using the specified build arguments, context, and Dockerfile.

    ```yaml
    - name: Build and push Docker image
      id: build-and-push
      uses: docker/build-push-action@v5
      with:
        push: true
        context: ./assistant/backend
        file: ./assistant/backend/Dockerfile
        build-args: |
          JFROG_USER=${{ secrets.JFROG_IDENTITY_USER }}
          JFROG_TOKEN=${{ secrets.JFROG_IDENTITY_TOKEN }}
        platforms: linux/amd64
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
    ```

## Conclusion

This documentation outlines the steps to set up and run the release process workflow for your backend service. Ensure that all the required secrets and configurations are properly set in your GitHub repository for the workflow to execute successfully. If you encounter any issues, review the logs for each step to identify and resolve errors.
