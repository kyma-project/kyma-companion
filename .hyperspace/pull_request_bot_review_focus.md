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

---

## Exception Leakage in Logging and HTTP Responses

Flag any code that embeds exception objects in log messages or returns exception details in HTTP responses.

### Rule 1 — No explicit exception interpolation in log calls

`logger.exception(...)` already captures and appends the full traceback automatically. `logger.error(...)` should only be used for simple messages without exception context; if exception context is needed, use `logger.exception(...)` instead. Embedding the exception in the message string is redundant and produces duplicate or incomplete error output.

**Flag any of the following patterns:**

```python
# BAD — redundant interpolation in logger.exception
logger.exception(f"Something failed: {e}")
logger.exception(f"Something failed: {str(e)}")
logger.exception("Something failed: %s", e)

# BAD — embedding exception in logger.error when logger.exception should be used
logger.error(f"Something failed: {e}")
logger.error(f"Something failed: {str(e)}")
logger.error("Something failed: %s", e)
```

**Expected pattern:**

```python
# GOOD — clean message, traceback appended automatically
logger.exception("Something failed")

# GOOD — logger.error with a plain message (no exception context needed)
logger.error("Validation failed for field X")
```

### Rule 2 — No exception details in HTTP response bodies

Exception messages must not be forwarded to HTTP clients. Leaking internal error details (stack traces, exception strings, library internals) can expose sensitive implementation information.

**Flag any of the following patterns:**

```python
# BAD — exception forwarded to client
raise HTTPException(status_code=500, detail=str(e))
raise HTTPException(status_code=500, detail=f"Error: {e}")
return JSONResponse(status_code=500, content={"error": str(e)})
```

**Expected pattern:**

```python
# GOOD — generic message to client, full detail captured in logs
logger.exception("Unexpected error processing request")
raise HTTPException(status_code=500, detail="Internal server error")
```

### Scope

- Applies to all Python source files (`.py`) in the PR diff.
- Both new code and modifications to existing code are in scope.
- Test files are **not** in scope.
