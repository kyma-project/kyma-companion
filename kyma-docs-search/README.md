# kyma-docs-search

Search service over indexed Kyma documentation (pgvector). Pipeline: optional LLM query expansion,
dense search, reciprocal rank fusion (k=60), optional LLM reranking. API: `api/openapi.yaml`.
Shared POC contract: `docs/poc-contract.md`.

## Run

```bash
CONFIG_PATH=/path/to/config.json \
DOCS_SEARCH_PG_DSN=postgres://postgres:postgres@localhost:5433/docs \
DOCS_SEARCH_PORT=8081 \
go run ./cmd/server
```

`CONFIG_PATH` is a kyma-companion `config.json` (`AICORE_*`, `models`, `MAIN_EMBEDDING_MODEL_NAME`,
`MAIN_MODEL_MINI_NAME`). `DOCS_SEARCH_PG_DSN` and `DOCS_SEARCH_PORT` (default 8081) may be set in the
file or as env vars; env vars win. On startup the service embeds one string to learn the model dimensions;
`/readyz` returns 503 unless the DB is reachable, a current run exists, and its model and dimensions match.

## Examples

```bash
curl localhost:8081/healthz
curl localhost:8081/readyz
curl localhost:8081/v1/status
curl -s localhost:8081/v1/search -d '{"query":"How do I enable a Kyma module?","top_k":3}'
curl -s localhost:8081/v1/search -d '{"query":"How do I enable a Kyma module?","top_k":3,"expand_queries":true}'
curl -s localhost:8081/v1/search -d '{"query":"How do I enable a Kyma module?","top_k":3,"expand_queries":true,"rerank":true,"filters":{"module":["telemetry-manager"]}}'
```

`score_type` is `cosine` (single query), `rrf` (several queries) or `llm` (reranked).

## Docker

```bash
docker build -t kyma-docs-search .
```

## Dev seed

`go run ./cmd/devseed up|down` creates/removes a throwaway 3-chunk run `00000000000000_seed00` for local testing.
