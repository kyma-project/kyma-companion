---
name: update-py-deps
description: Update all Python dependencies across the kyma-companion Poetry subprojects, one at a time. For each dependency: update to latest (fall back to minor/patch on conflicts), run pre-commit-check, fix issues, commit.
---

# Update Dependencies Skill

You are performing a systematic dependency update across the kyma-companion Poetry subprojects.

## Zero-interaction execution

**CRITICAL**: This skill must run to completion with zero user interactions. Never pause to ask questions. Never wait for approval. If something fails, fix it and continue.

**Do not do any setup or discovery steps.** Do not check for config files, do not explore the repo structure, do not read pyproject.toml before starting. The subproject layout is known (see below). Start immediately by reading `pyproject.toml` in the root subproject to identify the first dependency to update.

**One dependency = one commit.** Never batch multiple deps into a single commit. The only exception is when updating dep X forces a co-update of dep Y due to conflicts — in that case update both in one `poetry add` call and one commit, and name both in the commit message.

For each dependency update, run the helper script (pre-approved, no prompt):

```bash
bash .claude/skills/update-py-deps/update-dep.sh <subproject_dir> <pkg>
# with a group flag:
bash .claude/skills/update-py-deps/update-dep.sh <subproject_dir> <pkg> --group test
# with a specific version (conflict fallback):
bash .claude/skills/update-py-deps/update-dep.sh <subproject_dir> "<pkg>@^1.2"
```

The script: captures old version, runs `poetry add <pkg>@latest [extra args]`, captures new version, runs `pre-commit-check`, commits with message `deps: update <pkg> from v<old> to v<new>`. Defaults to `@latest`; pass a version suffix to override (e.g. `"pkg@^1.2"`).

If `pre-commit-check` fails due to source code issues, fix the files (Edit tool), then run:

```bash
bash .claude/skills/update-py-deps/update-dep.sh <subproject_dir> <pkg>
```

again from scratch (it re-adds and re-checks). If the fix only needs a re-check without re-adding (e.g. the dep is already added but pre-commit-check failed), run `update-dep.sh` anyway — `poetry add` will be a no-op if the version is already correct.

## Subprojects

There are 3 subprojects, each with their own `pyproject.toml` and `poetry.lock`:

- root (`.`)
- `doc_indexer/`
- `tests/blackbox/`

Process in this order: **root → doc_indexer → tests/blackbox**

Each subproject has a `poe pre-commit-check` target (sort, lint, typecheck, format, unit tests). Run all `poetry` and `poe` commands via `poetry run poe ...` (poe is not on PATH directly).

## Process — repeat for each dependency

1. **Read `pyproject.toml`** to find the next dependency to update
2. **Update + check + commit**: run the helper script
3. **Fix any source issues** with Edit tool if needed, then re-run `update-dep.sh`
4. **Move to the next dependency**

## Rules

- Update to latest version when possible; fall back to latest minor/patch only on conflicts
- Auto-fixes from ruff (format/lint) are applied by `pre-commit-check` automatically — `git add -A` picks them up
- Never skip a failing check — fix it before moving on
- Use `poetry add` not `poetry update`
- If `poetry add <pkg>@latest` fails due to conflicts, retry with a pinned version: `bash .claude/skills/update-py-deps/update-dep.sh <subproject_dir> "<pkg>@^X.Y"` (let poetry resolve the latest compatible)
- Skip a dependency if it's already at latest (poetry reports "No dependencies to install or update" and version unchanged)

## Dependency order within each subproject

`[project.dependencies]` first, then `[tool.poetry.group.test.dependencies]`, then `[tool.poetry.group.dev.dependencies]`.

## Commit message format

`deps: update <package> from v<old> to v<new>`

For forced co-updates: `deps: update <pkg1> from v<old> to v<new>, <pkg2> from v<old> to v<new>`
