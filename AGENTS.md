# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Codex, etc.) when working in this repository.

## Project Overview

**Kyma Companion** is a FastAPI-based AI assistant ("Joule") for Kyma and Kubernetes. It uses a multi-agent architecture built on LangGraph, backed by Redis for conversation state and HANA DB for RAG.

- **Language:** Python 3.13
- **Package manager:** Poetry
- **Task runner:** `poethepoet` (`poe`)
- **Key frameworks:** FastAPI, LangGraph, LangChain, SAP AI SDK

## Repository Layout

```
src/                        # Application source
  agents/                   # LangGraph multi-agent system
    common/                 # Base classes, state models, shared utilities
    supervisor/             # Supervisor agent (planner + finalizer)
    kyma/                   # Kyma-domain agent + tools
    k8s/                    # Kubernetes agent + tools
    memory/                 # Redis-backed LangGraph checkpointer
    cluster_diagnostics/    # Cluster diagnostic agents
    summarization/          # Token-aware message summarization
  routers/                  # FastAPI route handlers
  services/                 # Kubernetes, HANA, Redis, Langfuse integrations
  rag/                      # RAG retriever and reranker
  followup_questions/       # Follow-up question generation
  initial_questions/        # Initial question handling
  utils/                    # Logging, config, model factory
tests/
  unit/                     # Unit tests (fast, mocked)
  integration/              # Integration tests
  blackbox/                 # E2E tests (separate venv)
doc_indexer/                # Standalone document indexing service
.agents/skills/             # Claude Code developer workflow skills
.claude/                    # Claude Code configuration (skills symlink → .agents/skills)
.github/workflows/          # CI pipelines
```

## Development Commands

### Install dependencies

```bash
poetry install
poetry sync
```

### Run tests

```bash
poetry run poe test              # Unit tests (parallel)
poetry run poe test-integration  # Integration tests
```

### Lint and type-check

```bash
poetry run poe codecheck         # ruff + mypy + format check
poetry run poe lint-fix          # Auto-fix lint issues
poetry run poe code-fix          # Auto-fix lint + formatting
```

### Full pre-commit check (run before opening a PR)

```bash
poetry run poe pre-commit-check
```

This runs: dependency sort → auto-fix → codecheck → unit tests → workflow linting.

## Code Style

- Line length: **120**
- Formatter/linter: **Ruff** (config in `ruff.toml`)
- Type checker: **mypy** (strict, all files must pass)
- All public functions and classes require type annotations and docstrings
- McCabe complexity max: **10**; max statements per function: **50**

## Agent Architecture

The multi-agent graph (`src/agents/graph.py`) is built with LangGraph's `StateGraph`:

```
User Input
   └─► Gatekeeper       # Validates query (injection detection, domain check)
         └─► Supervisor
               ├─► Planner        # Breaks query into subtasks
               ├─► KymaAgent      # Handles Kyma-specific questions
               ├─► KubernetesAgent # Handles K8s questions
               └─► Finalizer      # Formats final response
```

**State classes** (Pydantic, in `src/agents/common/state.py`):
- `CompanionState` — top-level graph state
- `BaseAgentState` — shared state for sub-agents
- `SubTask`, `Plan`, `UserInput`, `GatekeeperResponse`

**Persistence:** Redis-backed checkpointer (`src/agents/memory/async_redis_checkpointer.py`) stores conversation state between requests.

**Summarization:** Token-aware summarization (`src/agents/summarization/`) keeps context within configured limits (`SUMMARIZATION_TOKEN_LOWER_LIMIT`, `SUMMARIZATION_TOKEN_UPPER_LIMIT`).

## Adding or Modifying Agents

- Extend `BaseAgent` (`src/agents/common/agent.py`) for new sub-agents
- Register new node/edge names in `src/agents/common/constants.py`
- Wire the new agent into the graph in `src/agents/graph.py`
- Add corresponding unit tests under `tests/unit/agents/`

## PR Workflow

PR title must follow semantic prefixes: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `deps` (enforced by CI).

Available Claude Code skills under `.agents/skills/` to automate the PR workflow:

| Skill | Purpose |
|---|---|
| `commit-changes` | Stage, check for secrets, and commit |
| `create-github-pr` | Run pre-commit checks, push, and open a PR |
| `pr-description` | Generate a PR description from the template and branch diff |
| `address-review-comments` | Pull and triage review comments |
| `update-py-deps` | Update Python dependencies across all subprojects |

Invoke via `/commit-changes`, `/create-github-pr`, etc. in Claude Code.

## CI Labels

Add these labels to a PR to trigger additional test suites:

| Label | Test suite |
|---|---|
| `run-integration-test` | Integration tests |
| `evaluation requested` | Evaluation tests (deepeval/ragas) |
| `api-tests` | API tests |

## Gate approvals

The `e2e` GitHub environment requires manual approval from an `ai-force` team member before integration-test jobs run. Use the helper script to approve all pending gates for a PR in one command:

```bash
./scripts/shell/approve-integration-gates.sh <pr-number>
# e.g.
./scripts/shell/approve-integration-gates.sh 1265
```

The script finds every workflow run associated with the PR, checks each for pending deployments, and approves any environment where `current_user_can_approve` is true. It prints a summary of what was approved and exits non-zero if no runs are found.

To approve gates for a fork of the repo, pass the full `org/repo` as a second argument:

```bash
./scripts/shell/approve-integration-gates.sh 1265 kyma-project/kyma-companion
```

**Manual fallback** (for a single run):

```bash
# 1. Find pending runs
gh pr checks <pr-number> --repo kyma-project/kyma-companion 2>&1 | grep pending

# 2. Check which environments need approval
gh api repos/kyma-project/kyma-companion/actions/runs/<run-id>/pending_deployments

# 3. Approve (environment ID from step 2)
gh api --method POST repos/kyma-project/kyma-companion/actions/runs/<run-id>/pending_deployments \
  --input - <<'EOF'
{"environment_ids":[<env-id>],"state":"approved","comment":"Approved"}
EOF
```
