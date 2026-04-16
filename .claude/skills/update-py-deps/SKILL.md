---
name: update-py-deps
description: Update all Python dependencies across the kyma-companion Poetry subprojects, one at a time. For each dependency: update to latest (fall back to minor/patch on conflicts), run pre-commit-check, fix issues, commit.
---

# Update Dependencies Skill

You are performing a systematic dependency update across the kyma-companion Poetry subprojects.

## Zero-interaction execution

**CRITICAL**: This skill must run to completion with zero user interactions. Never pause to ask questions. Never wait for approval. If something fails, fix it and continue.

**Do not do any setup or discovery steps.** Do not check for config files, do not explore the repo structure, do not read pyproject.toml before starting. The subproject layout is known (see below). Start immediately by reading `pyproject.toml` in the root subproject to identify the first dependency to update.

**Batch as much work as possible into a single Bash call.** Never split into multiple Bash calls what can be done in one.

**One dependency = one commit.** Never batch multiple deps into a single commit. The only exception is when updating dep X forces a co-update of dep Y due to conflicts — in that case update both in one `poetry add` call and one commit, and name both in the commit message.

For each dependency update, use a single Bash call like this pattern:

```bash
cd /path/to/subproject && \
  OLD=$(poetry show <pkg> --no-ansi | awk '/^version/{print $3}') && \
  poetry add "<pkg>@latest" && \
  NEW=$(poetry show <pkg> --no-ansi | awk '/^version/{print $3}') && \
  poetry run poe pre-commit-check && \
  git add -A && \
  git commit -m "deps: update <pkg> from v${OLD} to v${NEW}"
```

If `pre-commit-check` fails due to source code issues, fix the files (Edit tool), then run a second single Bash call with `pre-commit-check && git add -A && git commit`.

## Subprojects

There are 3 subprojects, each with their own `pyproject.toml` and `poetry.lock`:

- root (`.`)
- `doc_indexer/`
- `tests/blackbox/`

Process in this order: **root → doc_indexer → tests/blackbox**

Each subproject has a `poe pre-commit-check` target (sort, lint, typecheck, format, unit tests). Run all `poetry` and `poe` commands via `poetry run poe ...` (poe is not on PATH directly).

## Process — repeat for each dependency

1. **Identify current + latest version** in one Bash call
2. **Update + check + commit** in one Bash call (the pattern above)
3. **Fix any source issues** with Edit tool if needed, then re-run check+commit in one Bash call
4. **Move to the next dependency**

## Rules

- Update to latest version when possible; fall back to latest minor/patch only on conflicts
- Auto-fixes from ruff (format/lint) are applied by `pre-commit-check` automatically — `git add -A` picks them up
- Never skip a failing check — fix it before moving on
- Use `poetry add` not `poetry update`
- If `poetry add <pkg>@latest` fails due to conflicts, try without `@latest` to let poetry resolve, or pin to latest compatible version
- Skip a dependency if it's already at latest (poetry reports "No dependencies to install or update" and version unchanged)

## Dependency order within each subproject

`[project.dependencies]` first, then `[tool.poetry.group.test.dependencies]`, then `[tool.poetry.group.dev.dependencies]`.

## Commit message format

`deps: update <package> from v<old> to v<new>`

For forced co-updates: `deps: update <pkg1> from v<old> to v<new>, <pkg2> from v<old> to v<new>`

$ARGUMENTS
