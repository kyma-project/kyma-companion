# Custom Review Focus

## Security Gate for `pull_request_target` Workflows

Any GitHub Actions workflow triggered by `pull_request_target` **must** enforce the codeowner-authorization gate. Flag a violation if any of the following are true:

1. **Missing `authorize` job** — The workflow does not define an `authorize` job that uses  
   `kyma-project/kyma-companion/.github/actions/check-codeowner-auth@main`.
2. **Broken `needs` chain** — Any job in the workflow does not depend on `authorize` (directly or transitively through other jobs that themselves require `authorize`).
3. **Gate removed or weakened** — A PR modifies an existing `pull_request_target` workflow and removes or bypasses the `authorize` job or its `needs` dependency.

### Expected Pattern

```yaml
jobs:
  authorize:
    runs-on: ubuntu-latest
    steps:
      - uses: kyma-project/kyma-companion/.github/actions/check-codeowner-auth@main
        with:
          github-token: ${{ secrets.GIT_BOT_TOKEN }}

  # Every subsequent job must include `needs: authorize`
  # (directly, or transitively via another job that needs authorize)
  build:
    needs: authorize
    ...
```

### Scope

- Applies to **new, modified, and existing** workflow files under `.github/workflows/`.
- Only workflows with `pull_request_target` in their `on:` trigger are in scope.
- Workflows using only `pull_request`, `push`, `schedule`, or `workflow_dispatch` are **not** in scope.
