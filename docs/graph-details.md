# Kyma Companion LangGraph Architecture

## Overview

The Kyma Companion uses a hierarchical multi-agent architecture built with [LangGraph](https://langchain-ai.github.io/langgraph/). There is one **parent graph** (`CompanionGraph`) and three **subgraphs** — `Supervisor`, `KymaAgent`, and `KubernetesAgent`. Each subgraph is compiled independently and referenced as a node in the parent graph.

---

## Graph Diagrams

### Parent Graph (`CompanionGraph`)

```
                    ┌─────────────────────────┐
                    │         ENTRY            │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   InitialSummarization   │  ← Condense old messages
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │        Gatekeeper        │  ← Security + routing gate
                    └────────────┬─────────────┘
                    (next = ?)   │
             ┌───────────────────┼───────────────────┐
             │                                       │
    (forward_query=True)                  (direct answer or blocked)
             │                                       │
  ┌──────────▼──────────┐               ┌────────────▼──────────┐
  │     Supervisor      │               │          END           │
  │     (subgraph)      │               └───────────────────────┘
  └─────────────────────┘
    dispatches to members
    ┌──────┬──────┬──────┐
    │      │      │      │
  Kyma   K8s  Common   END
  Agent  Agent  Node
    │      │      │
    └──────┴──────┘
             │ (all report back via)
    ┌────────▼────────┐
    │  Summarization  │  ← Compress messages after each agent
    └────────┬────────┘
       (error?)
    ┌─────────────────┐
    │  No → Supervisor│  (loop back)
    │  Yes → END      │
    └─────────────────┘
```

### Supervisor Subgraph (`SupervisorAgent._build_graph`)

```
          START
            │
   ┌────────▼────────────────┐
   │   decide_entry_point    │  ← Inspect subtask state
   └──┬──────────┬──────────┬┘
      │          │          │
   PLANNER    ROUTER    FINALIZER
      │          │          │
  (plan)    (dispatch)  (synthesize)
      │          │          │
   ┌──▼──────────▼──┐        │
   │  decide_route  │        │
   │  _or_exit      │        │
   └──┬─────────────┘        │
      │                      │
   ROUTER ──── FINALIZER ────┘
                 │
                END
```

### Agent Subgraph (`BaseAgent._build_graph`) — shared by KymaAgent & KubernetesAgent

```
          START
            │
  ┌─────────▼──────────┐
  │  subtask_selector  │  ← Find my pending subtask
  └──────┬─────────────┘
         │  (no task) → finalizer
         │  (task found)
  ┌──────▼──────────┐
  │      agent      │  ← LLM with bound tools
  └──────┬──────────┘
         │  (no tool calls) → finalizer
         │  (tool calls)
  ┌──────▼──────────┐
  │  Summarization  │  ← Compress agent messages if needed
  └──────┬──────────┘
         │  (error) → END
         │  (ok)
  ┌──────▼──────────┐
  │     tools       │  ← Execute tool calls
  └──────┬──────────┘
         │
         └─────────────► agent  (loop)

  finalizer ──────────► END
```

---

## Node Descriptions

### Parent Graph Nodes

#### `InitialSummarization`

- **Type:** Summarization node (same logic as `Summarization`)
- **Purpose:** On every new request, checks whether the accumulated message history exceeds the token upper limit. If it does, it summarizes older messages into a `messages_summary` field and removes them from the state, keeping only the most recent messages that fit within `SUMMARIZATION_TOKEN_LOWER_LIMIT`.
- **Model:** `gpt-4o-mini`
- **Trigger:** Always the entry point of the parent graph.

#### `Gatekeeper`

- **Type:** Custom LLM chain with structured output (`GatekeeperResponse`)
- **Purpose:** Acts as the first line of defence and query classifier before any expensive agent work begins. It:
  1. **Detects prompt injection** — blocks any attempt to override instructions via system fields (namespace, resource_name, etc.)
  2. **Detects security threats** — blocks requests for attack payloads, RCE, SQL injection, etc.
  3. **Classifies** the query into one of: `Kyma`, `Kubernetes`, `Programming`, `About You`, `Greeting`, `Irrelevant`
  4. **Answers greetings directly** without forwarding.
  5. **Answers Programming / About You queries** directly using its own LLM response.
  6. **Answers past-tense Kyma/K8s queries from conversation history** if a full answer already exists.
  7. **Forwards** present-tense Kyma/K8s queries to the Supervisor.
  8. **Rejects** everything else (returns a fixed "outside my domain" message).
- **Model:** `gpt-4.1` (full model — security-critical path)
- **Output fields:** `is_prompt_injection`, `is_security_threat`, `category`, `direct_response`, `is_user_query_in_past_tense`, `answer_from_history`, `forward_query`

#### `Supervisor` (subgraph — see below)

Receives the forwarded query and orchestrates the worker agents.

#### `KymaAgent` (subgraph — see below)

Handles all Kyma-domain subtasks.

#### `KubernetesAgent` (subgraph — see below)

Handles all Kubernetes-domain subtasks.

#### `Common`

- **Type:** Simple LLM chain (no tools)
- **Purpose:** Handles subtasks classified as `Common` — general programming questions, conceptual explanations, or anything not requiring cluster access.
- **Prompt:** Receives conversation history + the subtask description and generates a direct text response.
- **Model:** `gpt-4o-mini`

#### `Summarization`

- **Type:** Summarization node
- **Purpose:** Called after every agent (Kyma, K8s, Common) completes its subtask. Checks whether the total message token count exceeds `SUMMARIZATION_TOKEN_UPPER_LIMIT`. If so, summarizes and trims older messages. Sets `next = Supervisor` so the loop continues. If an error occurred during summarization, transitions to `END`.
- **Model:** `gpt-4o-mini`

---

### Supervisor Subgraph Nodes

#### `Planner`

- **Purpose:** Breaks the user query into an ordered list of `SubTask` objects, each assigned to `KymaAgent`, `KubernetesAgent`, or `Common`.
- **Logic:**
  - Analyzes conversation history for follow-up context.
  - Cluster-wide queries → assign to **both** agents.
  - Namespace-wide queries → assign to **both** agents with namespace-specific descriptions.
  - Mixed-domain queries → split by domain.
  - Domain-specific queries → single agent.
  - Ambiguous → defaults to `KymaAgent`.
  - General/programming → assigns to `Common`.
- **Model:** `gpt-4o-mini`
- **Output:** A `Plan` with a list of `SubTask` objects (description, task_title, assigned_to, status=pending)

#### `Router`

- **Purpose:** Pure logic node (no LLM). Iterates through `subtasks` to find the first `PENDING` one and sets `next` to the assigned agent. If no pending subtasks remain, routes to `Finalizer`.

#### `Finalizer`

- **Purpose:** Synthesizes agent responses into a single coherent final answer for the user. Strictly follows these rules:
  - **Never** generates original content beyond what agents provided.
  - **Never** fills knowledge gaps.
  - Filters out executable malicious security content from responses.
  - Wraps new YAML in `<YAML-NEW>...</YAML-NEW>` tags and update YAML in `<YAML-UPDATE>...</YAML-UPDATE>` tags.
  - If all agents failed → returns a standard failure message.
  - After generating, runs through `ResponseConverter` to post-process any K8s resource links.
- **Model:** `gpt-4.1` (full model — response quality critical)

---

### Agent Subgraph Nodes (shared by KymaAgent & KubernetesAgent)

#### `subtask_selector`

Scans `state.subtasks` for a task assigned to this agent with status `PENDING`. If found, stores it in `my_task` and proceeds to `agent`. If none found, sets `is_last_step=True`, outputs "All my subtasks are already completed", and routes to `finalizer`.

#### `agent`

Invokes the LLM (with bound tools) on the current `my_task.description` plus filtered message history. Before calling the LLM, if the last message is a `ToolMessage`, checks whether the tool response exceeds `TOOL_RESPONSE_TOKEN_COUNT_LIMIT` and summarizes it in chunks if needed. If `remaining_steps <= 3`, terminates early to avoid recursion overflow. If `is_last_step` and response still contains tool calls, returns "I need more steps" instead of looping.

#### `Summarization` (agent-level)

Same logic as the parent-graph summarization but scoped to `agent_messages` and `agent_messages_summary`. Triggered when the `agent` node decides it needs to call tools.

#### `tools`

LangGraph `ToolNode` that executes the tool calls from the last `AIMessage`. `handle_tool_errors=True` — catches tool exceptions and returns them as `ToolMessage` content so the agent can retry.

#### `finalizer`

Marks `my_task` as `COMPLETED` (or keeps `ERROR` status if it errored). Prepends the subtask description to the last agent message content for traceability. Cleans up `agent_messages` from the state, promoting only the final result to the parent `messages` list.

---

## Tools Available to Each Agent

### KymaAgent Tools

| Tool | Description |
|---|---|
| `fetch_kyma_resource_version` | Discovers the current API group/version for a Kyma resource kind (e.g. `Function`, `APIRule`). Also warns if the version is deprecated. Uses the K8s API discovery endpoint. `k8s_client` is injected from state. |
| `kyma_query_tool` | Executes a raw `GET` against the Kubernetes API server using a full URI path (e.g. `/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions`). Returns the resource JSON. `k8s_client` is injected from state. |
| `search_kyma_doc` | RAG search over official Kyma documentation. Returns the top-5 most relevant document chunks. Backed by a `RAGSystem` using `text-embedding-3-large`. Returns "No relevant documentation found." if nothing passes the relevance threshold. |

**Tool flow defined in agent instructions:**

```
Troubleshooting / status checks (resource info unknown):
  fetch_kyma_resource_version → kyma_query_tool → search_kyma_doc

Troubleshooting / status checks (resource info known):
  kyma_query_tool → search_kyma_doc

On 404 from kyma_query_tool:
  kyma_query_tool (error) → fetch_kyma_resource_version → kyma_query_tool (retry) → search_kyma_doc

Conceptual / non-troubleshooting queries:
  search_kyma_doc only
```

### KubernetesAgent Tools

| Tool | Description |
|---|---|
| `k8s_query_tool` | Executes a raw `GET` against the Kubernetes API server using a full URI path. Sanitizes the response (e.g. removes the `data` field of `Secret` objects). `k8s_client` is injected from state. |
| `fetch_pod_logs_tool` | Fetches the last **10 lines** of current and previous logs for a specific pod container. Returns a structured result with diagnostic context if current logs are unavailable. |

### Common Node

Has **no tools**. Answers directly from LLM knowledge and conversation history.

---

## Configuration & Context Overloading Restrictions

These guardrails prevent runaway token usage, infinite loops, and context window overloading.

### Summarization Thresholds (message history)

| Setting | Default | Description |
|---|---|---|
| `SUMMARIZATION_TOKEN_UPPER_LIMIT` | **3,000** tokens | If total message history exceeds this, summarization is triggered. |
| `SUMMARIZATION_TOKEN_LOWER_LIMIT` | **2,000** tokens | Messages are trimmed from the front until the remainder fits within this limit. Older messages become a rolling summary. |

These apply at **two levels**:
1. The **parent graph** `InitialSummarization` / `Summarization` nodes manage `messages` / `messages_summary`.
2. The **agent subgraphs** have their own `agent_messages` / `agent_messages_summary` with the same thresholds.

### Tool Response Summarization

| Setting | Default | Description |
|---|---|---|
| `TOOL_RESPONSE_TOKEN_COUNT_LIMIT` | **10,000** tokens | If a tool response exceeds this, it is split into chunks and summarized before being fed back to the LLM. |
| `TOTAL_CHUNKS_LIMIT` | **2** chunks | Maximum chunks a tool response can be split into. If more are required, the request is rejected and the user is told the query is "too broad". |

When `TOTAL_CHUNKS_LIMIT` is exceeded, the agent returns:
> *"Your request is too broad and requires analyzing more resources than allowed at once. Please specify a particular resource you'd like to analyze so I can assist you more effectively."*

### Agent Recursion / Step Limits

| Setting | Default | Description |
|---|---|---|
| `BaseAgentState.remaining_steps` | **25** steps | LangGraph managed counter. Decrements on each node invocation within the agent subgraph. |
| `AGENT_STEPS_NUMBER` | **3** steps | If `remaining_steps <= 3`, the agent immediately stops tool calling and returns an error. This buffer ensures safe subgraph exit. |
| `GRAPH_STEP_TIMEOUT_SECONDS` | **180 s** | Per-step wall-clock timeout for both `KymaAgent` and `KubernetesAgent` subgraphs (set via `graph.step_timeout`). |

### Message Filtering

| Setting | Default | Description |
|---|---|---|
| `RECENT_MESSAGES_LIMIT` | **10** messages | The Planner's `filter_messages` call limits the conversation history passed to the Planner LLM to the last 10 messages. |

### Kubernetes API Pagination

| Setting | Default | Description |
|---|---|---|
| `K8S_API_PAGINATION_LIMIT` | **40** items | Number of items per page when listing K8s resources. |
| `K8S_API_PAGINATION_MAX_PAGE` | **1** page | Only the first page is ever retrieved, capping results at 40 items per query. |
| `POD_LOGS_TAIL_LINES_LIMIT` | **10** lines | Hard limit on log lines fetched per container in `fetch_pod_logs_tool`. |

### RAG Search

| Setting | Default | Description |
|---|---|---|
| `RAG_RELEVANCY_SCORE_THRESHOLD` | **0.5** | Documents below this cosine similarity score are filtered out before being returned to the agent. |
| `DEFAULT_TOP_K` | **5** | Maximum number of documentation chunks returned per `search_kyma_doc` call. |

### Token Usage Quota

| Setting | Default | Description |
|---|---|---|
| `TOKEN_LIMIT_PER_CLUSTER` | **5,000,000** tokens | Aggregate token usage cap per cluster ID, tracked in Redis. |
| `TOKEN_USAGE_RESET_INTERVAL` | **86,400 s** (24 h) | Rolling window after which the per-cluster counter resets. |
| `MAX_TOKEN_LIMIT_INPUT_QUERY` | **8,000** tokens | Maximum allowed tokens in a single input query (enforced at the API layer). |

### Security / Gatekeeper Restrictions

The Gatekeeper enforces **hard-coded behavioural rules** independently of the LLM classification output:

| Condition | Action |
|---|---|
| `is_prompt_injection = true` | Always returns `RESPONSE_QUERY_OUTSIDE_DOMAIN`. Never forwarded. |
| `is_security_threat = true` | Always returns `RESPONSE_QUERY_OUTSIDE_DOMAIN`. Never forwarded. |
| Category = `Irrelevant` | Returns `RESPONSE_QUERY_OUTSIDE_DOMAIN`. |
| Category = `Greeting` | Returns the fixed `RESPONSE_HELLO` constant. Never forwarded. |
| Category = `Kyma`/`Kubernetes` + past-tense + answer in history | Answered from history. Never forwarded (avoids redundant cluster calls). |
| Category = `Kyma`/`Kubernetes` (present-tense or no history answer) | Forwarded to Supervisor. |
| Category = `Programming` or `About You` | Answered directly by Gatekeeper LLM. |

### Tool Error Retry Policy

Defined in `TOOL_CALLING_ERROR_HANDLING` prompt, enforced behaviourally by the agent:

- On tool failure: analyse the error, check parameters, try a different tool or approach.
- **After 3 consecutive failed tool calls** — stop calling tools and report the failure clearly to the user.

---

## Model Assignment Summary

| Component | Model | Rationale |
|---|---|---|
| Gatekeeper | `gpt-4.1` | Security-critical; needs high accuracy for injection/threat detection |
| KymaAgent | `gpt-4.1` | Complex Kyma domain reasoning + multi-step tool use |
| KubernetesAgent | `gpt-4.1` | Complex K8s domain reasoning + multi-step tool use |
| Supervisor / Planner | `gpt-4o-mini` | Task decomposition; fast and cost-efficient |
| Finalizer | `gpt-4.1` | Needs full reasoning to faithfully synthesize agent responses |
| Common node | `gpt-4o-mini` | General questions; speed over capability |
| All Summarization nodes | `gpt-4o-mini` | Cost-efficient; runs frequently on every agent cycle |
