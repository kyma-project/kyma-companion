# Testing Strategy

## CI/CD Jobs Running on Pull Requests

Each pull request to the repository triggers the following CI/CD jobs that verify the Serverless Operator reconciliation logic and run integration tests of the Serverless module:

- `Markdown / link-check (pull_request)` - Checks if there are no broken links in the pull request `.md` files. For the configuration, see the [mlc.config.json](https://github.com/kyma-project/serverless/blob/main/.mlc.config.json) and the [markdown.yaml](https://github.com/kyma-project/serverless/blob/e36239e8315d7cce49eaa3ad1766f3261cef8af6/.github/workflows/markdown.yaml#L8) files.
- `Operator verify / lint (pull_request)` - Is responsible for the Operator linting and static code analysis. For the configuration, see the [operator-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/operator-verify.yaml#L19) file.
- `Serverless verify / lint (pull_request)` - Is responsible for the Serverless linting and static code analysis. For the configuration, see the [serverless-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/serverless-verify.yaml#L19) file.
- `Operator verify / unit-test (pull_request)` - Runs basic unit tests of Operator's logic. For the configuration, see the [operator-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/operator-verify.yaml#L30) file.
- `Serverless verify / unit-test (pull_request)` - Runs unit tests of Serverless's logic. For the configuration, see the [serverless-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/serverless-verify.yaml#L31) file.
- `Serverless verify / integration-test (pull_request)` - Runs the basic functionality integration and the `tracing`, `api-gateway`, `cloud-event` contract compatibility integration test suite for the Serverless in a k3d cluster. For the configuration, see the [serverless-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/serverless-verify.yaml#L40) file.

## CI/CD Jobs Running on the Main Branch

- `Serverless verify / integration-test (push)` - Runs the basic functionality integration and the `tracing`, `api-gateway`, and `cloud-event` contract compatibility integration test suite for Serverless in a k3d cluster. For the configuration, see the [serverless-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/serverless-verify.yaml#L40) file.
- `Operator verify / upgrade-test (push)` - Runs the upgrade integration test suite and verifies if the latest release can be successfully upgraded to the new (`main`) revision. For the configuration, see the [operator-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/operator-verify.yaml#L40) file.
- `Serverless verify / git-auth-integration-test (push)` - Runs the `GitHub` and `Azure DevOps` API and authentication integration test suite for Serverless. For the configuration, see the [serverless-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/serverless-verify.yaml#L67) file.
- `Operator verify / gardener-integration-test (push)` - Checks the installation of the Serverless module in the Gardener shoot cluster and runs basic integration tests of Serverless. For the configuration, see the [operator-verify.yaml](https://github.com/kyma-project/serverless/blob/main/.github/workflows/operator-verify.yaml#L60) file.

## CI/CD Jobs Running on a Schedule

- `Markdown / link-check` - Runs Markdown link check every day at 05:00 AM.