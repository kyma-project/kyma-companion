#!/usr/bin/env bash
# Live demo for the kyma-docs-search POC. Each step prints the command, runs it, shows a trimmed result,
# and waits for Enter. Set DEMO_NOPAUSE=1 to run straight through.
#
# Prerequisites (see demo/README.md): Postgres (pgvector-local) and Redis containers running, the search
# service on :8081, kyma-companion on :8000 in remote mode, jq installed.
set -u
SEARCH=${SEARCH_URL:-http://localhost:8081}
KC=${KC_URL:-http://localhost:8000}
PG="docker exec pgvector-local psql -U postgres -d docs"
B=$'\e[1m'; D=$'\e[2m'; R=$'\e[0m'; C=$'\e[36m'

step()  { printf '\n%s== %s%s\n' "$B" "$1" "$R"; }
say()   { printf '%s%s%s\n' "$D" "$1" "$R"; }
cmd()   { printf '%s$ %s%s\n' "$C" "$1" "$R"; }
pause() { [ "${DEMO_NOPAUSE:-}" = 1 ] || { printf '%s[Enter]%s' "$D" "$R"; read -r; }; }

# search <label> <json body>  -> prints score_type, queries, and one line per hit
search() {
  cmd "curl -s $SEARCH/v1/search -d '$2'"
  curl -s "$SEARCH/v1/search" -H 'Content-Type: application/json' -d "$2" | jq -r '
    "score_type: \(.score_type)   run: \(.index.run_id)",
    (if (.queries|length) > 1 then "queries: \(.queries|join(" | "))" else empty end),
    (.results[] | "  \(.score|tostring|.[0:6])  [\(.metadata.module)] \(.metadata.title)")'
}

step "1. What is being served"
say "GET /v1/status: which run, which model, which commits. The sources keys are the valid module filters."
cmd "curl -s $SEARCH/v1/status | jq"
curl -s "$SEARCH/v1/status" | jq '{run_id, embedding_model, dimensions, chunk_count, committed_at, modules: (.sources|keys|length), example: (.sources["api-gateway"])}'
pause

step "2. Dense search (default)"
say "Embedding similarity only. Exact CLI tokens get lost in prose about modules."
search dense '{"query":"kyma alpha module add","top_k":3}'
pause

step "3. Same question, hybrid"
say "BM25 over the same run, fused with dense. The CLI reference pages surface."
search hybrid '{"query":"kyma alpha module add","top_k":3,"mode":"hybrid"}'
pause

step "4. Filter by module"
say "filters.module restricts every mode. Unknown module gives an empty list, not an error."
search filtered '{"query":"kyma alpha module add","top_k":3,"mode":"hybrid","filters":{"module":["cli"]}}'
pause

step "5. Sparse only, exact identifier"
say "No embedding call at all. Only chunks containing the token come back."
search sparse '{"query":"keda-operator-metrics-apiserver","top_k":3,"mode":"sparse"}'
pause

step "6. Full pipeline: expansion and rerank"
say "Two LLM calls: four alternative queries, then relevance scores 0..1. This is what kyma-companion runs."
search full '{"query":"How do I enable the KEDA module and what resources does it need?","top_k":3,"mode":"hybrid","expand_queries":true,"rerank":true}'
pause

step "7. Validation"
cmd "curl -s $SEARCH/v1/search -d '{\"query\":\"\"}'"
curl -s -w '  -> HTTP %{http_code}\n' "$SEARCH/v1/search" -H 'Content-Type: application/json' -d '{"query":""}'
cmd "curl -s $SEARCH/v1/search -d '{\"query\":\"x\",\"mode\":\"magic\"}'"
curl -s -w '  -> HTTP %{http_code}\n' "$SEARCH/v1/search" -H 'Content-Type: application/json' -d '{"query":"x","mode":"magic"}'
pause

step "8. kyma-companion in remote mode"
say "Its own search endpoint, unchanged for callers. DOCS_SEARCH_URL is set, so no HANA, no local pipeline."
cmd "curl -s $KC/healthz | jq"
curl -s "$KC/healthz" | jq '{is_hana_healthy, is_redis_healthy}'
cmd "curl -s $KC/api/tools/kyma/search -d '{\"query\":\"How do I expose a workload with an APIRule and JWT?\"}'"
curl -s "$KC/api/tools/kyma/search" -H 'Content-Type: application/json' -d '{"query":"How do I expose a workload with an APIRule and JWT?"}' \
  | jq -r '.results[] | "  " + (split("\n")[0] | .[0:110])'
say "service log shows the same request arriving as POST /v1/search from the companion"
pause

step "9. The MCP door, same process"
say "Tool search_kyma_docs maps onto the same pipeline. Here with a module filter."
cmd "go run ./cmd/mcpcheck $SEARCH/mcp 'kyma alpha module add' cli"
(cd "$(dirname "$0")/.." && go run ./cmd/mcpcheck "$SEARCH/mcp" "kyma alpha module add" cli) | sed -n '1,2p;/^[0-9]\./,$p' | cut -c1-120
say "Claude Code: claude mcp add --transport http kyma-docs $SEARCH/mcp"
pause

step "10. Runs and the pointer"
say "One table per run, one row per run, exactly one current. The last two runs are kept."
cmd "$PG -c 'SELECT run_id, chunk_count, embedding_model, is_current, committed_at FROM docs_index_runs ORDER BY created_at'"
$PG -c "SELECT run_id, chunk_count, embedding_model, is_current, committed_at FROM docs_index_runs ORDER BY created_at"
pause

step "11. Rollback is one update"
PREV=$($PG -At -c "SELECT run_id FROM docs_index_runs WHERE NOT is_current ORDER BY committed_at DESC LIMIT 1")
CUR=$($PG -At -c "SELECT run_id FROM docs_index_runs WHERE is_current")
say "Flip the pointer to the previous run ($PREV), ask the service, flip back. The service re-reads the pointer within 30 s."
cmd "$PG -c \"BEGIN; UPDATE docs_index_runs SET is_current = false; UPDATE docs_index_runs SET is_current = true WHERE run_id = '$PREV'; COMMIT\""
$PG -q -c "BEGIN; UPDATE docs_index_runs SET is_current = false; UPDATE docs_index_runs SET is_current = true WHERE run_id = '$PREV'; COMMIT"
say "waiting for the service to notice..."
for _ in $(seq 1 35); do
  NOW=$(curl -s "$SEARCH/v1/status" | jq -r .run_id); [ "$NOW" = "$PREV" ] && break; sleep 1
done
cmd "curl -s $SEARCH/v1/status | jq '{run_id, chunk_count}'"
curl -s "$SEARCH/v1/status" | jq '{run_id, chunk_count}'
cmd "$PG -c \"BEGIN; UPDATE docs_index_runs SET is_current = false; UPDATE docs_index_runs SET is_current = true WHERE run_id = '$CUR'; COMMIT\""
$PG -q -c "BEGIN; UPDATE docs_index_runs SET is_current = false; UPDATE docs_index_runs SET is_current = true WHERE run_id = '$CUR'; COMMIT"
say "flipped back to $CUR"
pause

step "12. Indexer run summary (file writer, no database touched)"
say "Index the small e2e corpus to a file and render the summary that a GitHub Actions job page would show."
cmd "DOCS_WRITER=file DOCS_SUMMARY_PATH=/tmp/demo-summary.md poetry run python src/main.py index"
( cd "$(dirname "$0")/../../doc_indexer" && CONFIG_PATH=../config/config.json DOCS_PATH=./data DOCS_WRITER=file \
  DOCS_FILE_PATH=/tmp/demo-kyma_docs_{run_id}.json DOCS_SUMMARY_PATH=/tmp/demo-summary.md \
  poetry run python src/main.py index 2>/dev/null | jq -r 'select(.message|startswith("Index completed")) | .message' )
cat /tmp/demo-summary.md
pause

step "13. Soft copy: export the served index to a file"
say "Chunks and vectors, no re-embedding. Import it into any Postgres with: python src/main.py import --file ..."
cmd "poetry run python src/main.py export --from pgvector --file /tmp/demo-export.json"
( cd "$(dirname "$0")/../../doc_indexer" && CONFIG_PATH=../config/config.json DOCS_SEARCH_PG_DSN=postgres://postgres:postgres@localhost:5433/docs \
  poetry run python src/main.py export --from pgvector --file /tmp/demo-export.json 2>/dev/null | jq -r 'select(.message|startswith("Exported")) | .message' )
ls -lh /tmp/demo-export.json | awk '{print "  " $5 "  " $9}'
jq -c '.run | {run_id, embedding_model, dimensions, exported_from}' /tmp/demo-export.json
printf '\n%sdone%s\n' "$B" "$R"
