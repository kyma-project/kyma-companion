# Live demo

Start everything, then run `demo/demo.sh` and press Enter between steps (`DEMO_NOPAUSE=1` runs it straight through).

## Start

```bash
# containers
docker start pgvector-local redis-local

# search service (port 8081), from kyma-docs-search/
CONFIG_PATH=../config/config.json DOCS_SEARCH_PG_DSN=postgres://postgres:postgres@localhost:5433/docs DOCS_SEARCH_PORT=8081 go run ./cmd/server

# kyma-companion in remote mode (port 8000), from the worktree root; config.json must contain
# "DOCS_SEARCH_URL": "http://localhost:8081"
LOG_FORMAT=json poetry run python src/main.py
```

`config/config.json` needs working AI Core credentials (steps 6, 8 and 12 call AI Core). The `docs` database must hold a committed run with the full corpus; the small e2e corpus must be fetched to `doc_indexer/data` for step 12.

## Steps

| # | shows | calls |
|---|---|---|
| 1 | what is served, valid module filters | `GET /v1/status` |
| 2, 3 | dense vs hybrid on `kyma alpha module add` | `POST /v1/search` |
| 4 | module filter | `filters.module` |
| 5 | sparse on an exact identifier, no embedding call | `mode: sparse` |
| 6 | expansion + rerank, what kyma-companion runs | `expand_queries`, `rerank` |
| 7 | validation errors | 400s |
| 8 | kyma-companion unchanged for callers, no HANA | `POST /api/tools/kyma/search` |
| 9 | MCP tool on the same pipeline | `cmd/mcpcheck` |
| 10 | runs table and pointer | psql |
| 11 | rollback by flipping the pointer, service follows within 30 s | psql + `/v1/status` |
| 12 | indexer run summary, file writer only | `python src/main.py index` |
| 13 | export the served index to a file | `python src/main.py export` |

## Stop

```bash
lsof -ti:8000,8081 | xargs kill -9
```
