# Pre-hook Architecture

## Overview

Queries pass through a **HookChain** before reaching `CompanionAgent`. Any hook can short-circuit and return a direct response without invoking the agent.

```
HTTP POST /api/v1/conversations/{id}/messages
    │
    ▼
ConversationService.handle_request()
    │
    ├─ load history from Redis (once)
    │
    ▼
HookChain.run(query, history)
    │
    ├─ SecurityHook.run() ─┐  (parallel)
    │                       ├─ first block → cancel other, stream gatekeeper SSE, return
    └─ CategoryHook.run() ─┘
    │
    ▼ (all passed)
CompanionAgent.handle_message(history=preloaded)
    │
    ▼
tool-use loop → SSE stream
```

## Components

### `HookResult` (`agents/hooks/base.py`)

```python
@dataclass
class HookResult:
    blocked: bool
    direct_response: str = ""
```

Returned by every hook. `blocked=True` means short-circuit; `direct_response` is what gets streamed back.

### `IHook` (`agents/hooks/base.py`)

A `Protocol` that every hook implements:

```python
class IHook(Protocol):
    async def run(self, query: str, history: list[dict]) -> HookResult: ...
```

### `HookChain` (`agents/hooks/chain.py`)

Runs all hooks in parallel via `asyncio.wait(FIRST_COMPLETED)`. As soon as any hook returns `blocked=True`, the remaining tasks are cancelled and that result is returned immediately — no waiting for slower hooks to finish. If multiple hooks block simultaneously, the one earliest in the list wins. If all hooks pass, returns `HookResult(blocked=False)`.

This is a **fail-fast** design: the latency gain only applies to blocked queries (bad actors, greetings, OOD). For pass-through queries (Kyma/K8s) all hooks must complete regardless.

### `SecurityHook` (`agents/hooks/security.py`)

Calls the LLM with `SECURITY_HOOK_PROMPT` using structured output (`SecurityCheckResponse`).

```python
class SecurityCheckResponse(BaseModel):
    is_prompt_injection: bool
    is_security_threat: bool
```

Blocks with `RESPONSE_QUERY_OUTSIDE_DOMAIN` if either flag is `True`. **Fails open** on LLM error (passes through).

### `CategoryHook` (`agents/hooks/category.py`)

Calls the LLM with `CATEGORY_HOOK_PROMPT` using structured output (`CategoryCheckResponse`).

```python
class CategoryCheckResponse(BaseModel):
    category: Literal["Kyma", "Kubernetes", "Programming", "About You", "Greeting", "Irrelevant"]
    direct_response: str
```

Routing table:

| Category | Action |
|---|---|
| `Kyma`, `Kubernetes` | Forward to `CompanionAgent` |
| `Greeting` | Block → `RESPONSE_HELLO` |
| `Programming`, `About You` (with `direct_response`) | Block → `direct_response` |
| `Programming`, `About You` (empty) | Block → `RESPONSE_QUERY_OUTSIDE_DOMAIN` |
| `Irrelevant` | Block → `RESPONSE_QUERY_OUTSIDE_DOMAIN` |

**Fails open** on LLM error.

### `make_gatekeeper_event` (`utils/streaming.py`)

Formats a blocked response as an SSE event with `agent="Gatekeeper"` and `next="__end__"`.

## Key Design Decisions

**Parallel hooks with fail-fast.** Both hooks fire concurrently. For blocked queries the chain returns as soon as the faster hook completes, cancelling the slower one. For pass-through queries both must finish — no latency gain, but no regression either.

**Separate LLM calls per hook.** Security and category checks use different prompts and Pydantic models, keeping concerns cleanly separated and independently testable. The parallel execution means there is no sequential latency penalty for having two calls.

**Fail-open semantics.** Both hooks catch all exceptions and return `HookResult(blocked=False)`. A broken LLM call never blocks a legitimate user query.

**History loaded once.** `ConversationService.handle_request()` loads conversation history from Redis before the hook chain runs. The same history object is passed to `CompanionAgent`, avoiding a second Redis read.

**`model_mini` for hooks.** Both hooks use the smaller/cheaper model (same as the gatekeeper in the main branch).
