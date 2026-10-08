// devseed inserts or removes a throwaway index run for local testing. Usage: devseed [up|down]
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/kyma-project/kyma-docs-search/internal/aicore"
	"github.com/kyma-project/kyma-docs-search/internal/config"
)

const runID = "00000000000000_seed00"

func main() {
	ctx := context.Background()
	cfg, err := config.Load()
	if err != nil {
		log.Fatal(err)
	}
	conn, err := pgx.Connect(ctx, cfg.PGDSN)
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close(ctx)
	table := "docs_chunks_" + runID
	if len(os.Args) > 1 && os.Args[1] == "down" {
		must(conn.Exec(ctx, "DELETE FROM docs_index_runs WHERE run_id=$1", runID))
		must(conn.Exec(ctx, "DROP TABLE IF EXISTS "+table))
		fmt.Println("seed removed")
		return
	}
	ai := aicore.New(cfg.AICoreAuthURL, cfg.AICoreBaseURL, cfg.AICoreClientID, cfg.AICoreClientSecret,
		cfg.AICoreResourceGroup, cfg.EmbeddingModel, cfg.Deployments)
	texts := []string{
		"# Enable a Kyma module\nTo enable a Kyma module, add it to the Kyma custom resource in kyma-system or use the Kyma dashboard: Modules, Add, select the module and choose Add.",
		"# Telemetry module\nThe Telemetry module collects logs, traces and metrics from your workloads and ships them to an OTLP backend using LogPipeline, TracePipeline and MetricPipeline resources.",
		"# Serverless function\nA Serverless Function lets you run short code snippets in Kyma without managing containers. Create a Function resource with inline source and dependencies.",
	}
	mods := []string{"kyma-environment", "telemetry-manager", "serverless"}
	vecs, _, err := ai.Embeddings(ctx, texts)
	if err != nil {
		log.Fatal(err)
	}
	dims := len(vecs[0])
	must(conn.Exec(ctx, `CREATE TABLE IF NOT EXISTS docs_index_runs (run_id text PRIMARY KEY, table_name text NOT NULL,
		embedding_model text NOT NULL, dimensions integer NOT NULL, chunk_count integer NOT NULL DEFAULT 0,
		sources jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
		committed_at timestamptz, is_current boolean NOT NULL DEFAULT false)`))
	must(conn.Exec(ctx, fmt.Sprintf("CREATE TABLE %s (id bigserial PRIMARY KEY, content text NOT NULL, metadata jsonb NOT NULL, embedding vector(%d) NOT NULL)", table, dims)))
	for i, t := range texts {
		var sb strings.Builder
		sb.WriteByte('[')
		for j, f := range vecs[i] {
			if j > 0 {
				sb.WriteByte(',')
			}
			fmt.Fprintf(&sb, "%g", f)
		}
		sb.WriteByte(']')
		meta := fmt.Sprintf(`{"module":%q,"title":%q,"url":"https://example.invalid/%d"}`, mods[i], strings.SplitN(t, "\n", 2)[0][2:], i)
		must(conn.Exec(ctx, fmt.Sprintf("INSERT INTO %s (content, metadata, embedding) VALUES ($1,$2::jsonb,$3::vector)", table), t, meta, sb.String()))
	}
	must(conn.Exec(ctx, `INSERT INTO docs_index_runs (run_id, table_name, embedding_model, dimensions, chunk_count, committed_at, is_current)
		VALUES ($1,$2,$3,$4,3,now(),true)`, runID, table, cfg.EmbeddingModel, dims))
	fmt.Println("seed created, dims", dims)
}

func must(_ any, err error) {
	if err != nil {
		log.Fatal(err)
	}
}
