# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Codex, etc.) when working in this repository.

## Project Overview

**Kyma Companion** is a FastAPI-based AI assistant ("Joule") for Kyma and Kubernetes. It exposes a single ReAct agent via the [Agent-to-Agent (A2A)](https://github.com/google/a2a) protocol, backed by Redis for conversation history and HANA DB for RAG.

- **Language:** Python 3.14
- **Package manager:** Poetry
- **Task runner:** `poethepoet` (`poe`)
- **Key frameworks:** FastAPI, LangChain, A2A SDK, SAP AI SDK

## Repository Layout

```
src/                        # Application source
  agents/                   # Agent logic and tools
    common/                 # Shared utilities, data models, error handling
    kyma/                   # KymaReActAgent, tools (query, search, resource version)
    k8s/                    # Kubernetes tools (query, logs, overview)
    memory/                 # Redis-backed LLM usage tracking (token usage per cluster)
  routers/                  # FastAPI route handlers
    kyma_agent_a2a.py       # A2A protocol endpoint for the Kyma agent
    k8s_tools_api.py        # REST endpoints for K8s tools
    kyma_tools_api.py       # REST endpoints for Kyma tools
  services/                 # Kubernetes, HANA, Redis, Langfuse, encryption integrations
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

The application has a single agent: **`KymaReActAgent`** (`src/agents/kyma/react_agent.py`). It is a LangChain ReAct loop (Reason + Act) exposed over the [A2A protocol](https://github.com/google/a2a) via `src/routers/kyma_agent_a2a.py`.

```
A2A Client (e.g. Busola UI)
   └─► POST /api/agent/kyma/chat  (JSON-RPC message/send)
         └─► KymaAgentExecutor    # Decrypts cluster creds, loads Redis history
               └─► KymaReActAgent  # ReAct tool-calling loop
                     ├─► kyma_query_tool             # Fetch any K8s/Kyma resource
                     ├─► fetch_kyma_resource_version # Look up API version for a Kyma kind
                     ├─► k8s_overview_tool           # Cluster/namespace overview
                     ├─► fetch_pod_logs_tool         # Pod container logs
                     └─► search_kyma_doc             # RAG-based doc search
```

**A2A integration** (`src/routers/kyma_agent_a2a.py`):
- `KymaAgentExecutor` extends `a2a.server.agent_execution.AgentExecutor`
- `build_kyma_a2a_app()` creates a Starlette sub-app mounted at `/api/agent/kyma`
- Cluster credentials arrive in encrypted A2A message metadata (`x-session-id`, `x-encrypted-key`, `x-client-iv`, `x-target-cluster-encrypted`)
- Conversation continuity is keyed on the A2A `context_id` stored in Redis

**Redis memory** (`src/agents/memory/async_redis_checkpointer.py`):
- `AsyncRedisSaver` stores conversation history (list of messages) and tracks LLM token usage per cluster
- No longer a LangGraph checkpoint saver

**Tools also accessible as REST** (`/api/tools/k8s/*`, `/api/tools/kyma/*`):
- K8s: `POST /query`, `POST /pods/logs`, `POST /overview`
- Kyma: `POST /query`, `POST /resource-version`, `POST /search`

## Adding or Modifying the Agent

- Edit the ReAct loop in `src/agents/kyma/react_agent.py`
- Add new tools to `src/agents/kyma/tools/` or `src/agents/k8s/tools/`; bind them in `KymaReActAgent.__init__`
- Update prompts in `src/agents/kyma/prompts.py`
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
