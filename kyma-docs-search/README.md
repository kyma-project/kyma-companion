# kyma-docs-search

Search service over indexed Kyma documentation (pgvector). Pipeline: optional LLM query expansion,
dense, sparse (in-memory BM25) or hybrid search, reciprocal rank fusion (k=60), optional LLM reranking. API: `api/openapi.yaml`.
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

`mode` selects retrieval: `dense` (default), `sparse` (BM25) or `hybrid` (BM25 + dense via RRF), e.g.
`curl -s localhost:8081/v1/search -d '{"query":"ScaledObject","top_k":3,"mode":"hybrid"}'`. The BM25 index is held in
memory, built at startup and rebuilt in the background when the current run changes; sparse/hybrid return 503 until
the first build is done.

Filtering: `filters.module` (REST) and `modules` (MCP tool) restrict results to the given module names; the valid names are the keys of `sources` in `GET /v1/status`. An unknown module yields an empty result, not an error.

`score_type` is `cosine` (single dense query), `bm25` (single sparse query), `rrf` (several queries or hybrid) or `llm` (reranked).

## MCP server

The same process serves an MCP server (streamable HTTP) at `/mcp`, on the same port as the REST API.
Design principle: the MCP server contains no retrieval logic. It maps a tool call to the in-process pipeline
call that `POST /v1/search` uses (`internal/mcpserver`), so both doors always return the same results.

Tool `search_kyma_docs` -- input: `query` (required), `top_k` (1-50, default 5), `mode` (`dense|sparse|hybrid`,
default `hybrid`), `expand_queries` (default false), `rerank` (default false). Output: structured content
`{"results":[{title, content, source_url, score, module}]}` plus the same JSON as a text content block for clients
that ignore structured content. Pipeline errors come back as tool errors (`isError: true`), not transport errors.
`source_url` is `metadata.url`; callers must cite it.

Connect from an MCP client, e.g. Claude Code:

```bash
claude mcp add --transport http kyma-docs http://localhost:8081/mcp
```

Verify without curl, using the SDK client in `cmd/mcpcheck` (initializes, lists tools, calls the tool):

```bash
go run ./cmd/mcpcheck http://localhost:8081/mcp
```

Security: the POC has no auth. In production the MCP endpoint sits behind JWT (IAS/XSUAA on the ingress) and the
service applies per-caller policy. In the POC the MCP tool is the only unauthenticated door and must not be exposed
outside localhost.

## Docker

```bash
docker build -t kyma-docs-search .
```

## Dev seed

`go run ./cmd/devseed up|down` creates/removes a throwaway 3-chunk run `00000000000000_seed00` for local testing.

## Supply chain and image

`scripts/security-check.sh` runs the whole set and fails on any finding; `../doc_indexer/ci/service-security.yaml` is the CI draft (every PR and daily, because the databases move without a code change).

| check | what it proves | result 2026-10-07 |
|---|---|---|
| `go mod verify` | module contents match `go.sum` | all modules verified |
| `govulncheck ./...` | Go vulnerability DB, only for code paths this binary calls | no vulnerabilities |
| `docker build` | `CGO_ENABLED=0`, `-trimpath`, `-ldflags "-s -w"`: static, stripped, no build paths; `FROM scratch`; user 10001 | 13.6 MB, 4 layers |
| `trivy image` | OS packages (there are none), the 14 Go modules read from the binary's build info, secrets, misconfiguration | 0 findings |
| `govulncheck -mode=binary` | the shipped artifact, not the source tree | no vulnerabilities |

Why the image is small to defend: no shell, no package manager, no libc, no interpreter. The only things in it are the binary, the CA bundle, the time zone database and a one-line `/etc/passwd`. Scanners still see every dependency because Go embeds the module list in the binary (`go version -m`). Dependencies are kept current with `go get -u ./... && go mod tidy`; the five modules `go list -m -u all` still reports as outdated are test-only dependencies of dependencies and are not in the binary.
