# kyma-docs-search POC: shared contract

Three parties work against this document: the Python indexer (`doc_indexer/`, writer),
the Go service (`kyma-docs-search/`, reader + pipeline), and kyma-companion (`src/`, consumer).
Change this file first if you need to change the contract.

## Postgres (pgvector) layout

Written by the indexer, read by the service. One database, extension `vector`.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS docs_index_runs (
  run_id          text PRIMARY KEY,
  table_name      text NOT NULL,
  embedding_model text NOT NULL,
  dimensions      integer NOT NULL,
  chunk_count     integer NOT NULL DEFAULT 0,
  sources         jsonb NOT NULL DEFAULT '{}'::jsonb,   -- fetch manifest.json: {module: {url, commit}}
  created_at      timestamptz NOT NULL DEFAULT now(),
  committed_at    timestamptz,
  is_current      boolean NOT NULL DEFAULT false
);
-- at most one current run
CREATE UNIQUE INDEX IF NOT EXISTS docs_index_runs_one_current
  ON docs_index_runs (is_current) WHERE is_current;

-- one table per run, created by begin(run):
CREATE TABLE docs_chunks_<run_id> (
  id        bigserial PRIMARY KEY,
  content   text  NOT NULL,
  metadata  jsonb NOT NULL,
  embedding vector(<dimensions>) NOT NULL
);
-- no ANN index in the POC: pgvector `vector` HNSW/IVFFlat stop at 2000 dims,
-- text-embedding-3-large has 3072. Exact scan is fine for the demo corpus.
```

`run_id` format: `%Y%m%d%H%M%S` UTC + `_` + 6 lowercase hex, e.g. `20261007143012_a1f3c9`.
Only `[a-z0-9_]`, so `docs_chunks_<run_id>` is a valid unqualified identifier.

Writer semantics (indexer):
- `begin(run)`: insert the `docs_index_runs` row with `is_current=false`, create the chunk table.
- `write(batch)`: insert chunks; `content` is the chunk text (with the `# title` line prepended as the current indexer does), `metadata` is the chunk metadata dict, `embedding` the vector.
- `commit()`: in one transaction: `UPDATE docs_index_runs SET is_current=false WHERE is_current;`
  then `UPDATE docs_index_runs SET is_current=true, committed_at=now(), chunk_count=<n> WHERE run_id=<run>`.
  Afterwards drop chunk tables of runs that are neither current nor among the 2 most recent committed runs, and delete their rows.
- `abort()`: drop the chunk table and delete the row.

Reader semantics (service):
- "current run" = `SELECT ... FROM docs_index_runs WHERE is_current`. Cached in-process for 30 s.
- On startup and in `/readyz`: fail if there is no current run, or if its `embedding_model`/`dimensions`
  differ from the service config (`MAIN_EMBEDDING_MODEL_NAME`, dimensions from the first embedding call or 3072 for text-embedding-3-large).
- Dense search:
  ```sql
  SELECT content, metadata, 1 - (embedding <=> $1::vector) AS score
  FROM docs_chunks_<run_id>
  [WHERE metadata->>'module' = ANY($2)]
  ORDER BY embedding <=> $1::vector
  LIMIT $3
  ```
- The service never writes.

## Chunk metadata keys

Produced by `doc_indexer/src/indexing/metadata.py` + `adaptive_indexer.py`:
`module`, `path`, `repo`, `commit`, `url`, `title`, `doc_type`, `audience` (list), `heading`, `chunk_index`, `total_chunks`.
The service passes metadata through unchanged. Consumers read `url`, `title`, `module`, `source` (kc reranker; `source` may be absent).

## Pipeline (service), mirrors kyma-companion `src/rag/system.py`

Input: `query`, `top_k` (default 5), `expand_queries`, `rerank`, `filters.module`.

1. `queries = [query]`. If `expand_queries`: one chat completion on the mini model with the query generator prompt
   (copy from `src/rag/prompts.py` QUERY_GENERATOR_PROMPT_TEMPLATE + FOLLOWUP, `num_queries` = 4), structured output
   via tool call `{"queries": [string]}`; append, strip, drop empty, dedupe.
2. `candidate_k = max(top_k * 4, 10)` if more than one query or rerank, else `top_k`.
   Embed all queries in one embeddings call (input is a list). Dense search per query, concurrently.
3. If more than one query: merge with reciprocal rank fusion, `k = 60`, key = chunk content. `score_type = rrf`.
   If a single query and no rerank: `score_type = cosine`, scores are the cosine similarities.
4. If `rerank`: take the top `top_k + 3` candidates (kc behaviour), one chat completion on the mini model with the
   reranker prompt (copy from `src/rag/reranker/prompt.py`), structured output via tool call
   `{"documents": [{"id": "doc_<n>", "score": number}]}` (0.00-1.00; ids are assigned by the service as doc_1..doc_N, matching the copied Python prompt, unknown ids are dropped), sort desc, cut to `top_k`. `score_type = llm`.
   If the LLM call fails: fall back to the RRF/cosine order, keep the previous `score_type`, log a warning.
5. Cut to `top_k`. Return `results`, `queries`, `score_type`, `index{run_id, embedding_model, committed_at}`.

## AI Core (service and indexer both use the kyma-companion config.json)

Read `CONFIG_PATH` (JSON, kyma-companion format). Keys:
`AICORE_AUTH_URL`, `AICORE_BASE_URL`, `AICORE_CLIENT_ID`, `AICORE_CLIENT_SECRET`, `AICORE_RESOURCE_GROUP`,
`models: [{name, deployment_id, ...}]`, `MAIN_EMBEDDING_MODEL_NAME` (service; indexer uses `EMBEDDING_MODEL_NAME`), `MAIN_MODEL_MINI_NAME`.

Calls (see `/Users/I549741/claude/kyma/k8s-agent-tools/internal/rag/retriever.go` for a working Go implementation):
- token: `POST {AICORE_AUTH_URL}` body `grant_type=client_credentials`, Basic auth client id/secret; cache until expiry minus 60 s.
  NOTE: in this config.json `AICORE_AUTH_URL` already ends with `/oauth/token`; do not append it twice.
- deployment URL: `GET {AICORE_BASE_URL}/lm/deployments/{deployment_id}` with `Authorization: Bearer`, `AI-Resource-Group`; response `deploymentUrl`; cache.
- embeddings: `POST {deploymentUrl}/embeddings?api-version=2025-03-01-preview`, header `AI-Resource-Group`, body `{"input": [..]}`.
  The `api-version` query parameter is required (404 without).
- chat: `POST {deploymentUrl}/chat/completions?api-version=2025-03-01-preview`, body `messages` + `tools` + `tool_choice: {"type":"function","function":{"name":...}}`;
  result in `choices[0].message.tool_calls[0].function.arguments` (JSON string).

## New config keys

| key | used by | example |
|---|---|---|
| `DOCS_WRITER` | indexer | `pgvector` (default `hana`; also `file`) |
| `DOCS_SEARCH_PG_DSN` | indexer, service | `postgres://postgres:postgres@localhost:5433/docs` |
| `DOCS_SEARCH_PORT` | service | `8081` |
| `DOCS_SEARCH_URL` | kyma-companion | `http://localhost:8081` (set -> remote search, unset -> local HANA pipeline) |

## Local demo environment

- Postgres: `docker start pgvector-local` (pgvector/pgvector:pg17, port 5433, db `docs`, user `postgres`, password `postgres`, extension `vector` created).
- config: `config/config.json` in the worktree (gitignored). Indexer reads it via `CONFIG_PATH=../config/config.json` from `doc_indexer/`.
- small corpus: `doc_indexer/e2e_docs_sources.json` (`DOCS_SOURCES_FILE_PATH`).
- demo flow: fetch -> index (pgvector) -> service -> `curl /v1/search` -> kc with `DOCS_SEARCH_URL` -> ask the companion.
