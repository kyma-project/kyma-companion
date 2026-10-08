// Package pipeline implements query expansion, dense retrieval, RRF and LLM reranking.
package pipeline

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sort"
	"strings"
	"sync"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"

	"github.com/kyma-project/kyma-docs-search/internal/aicore"
	"github.com/kyma-project/kyma-docs-search/internal/sparse"
	"github.com/kyma-project/kyma-docs-search/internal/store"
	"github.com/kyma-project/kyma-docs-search/internal/telemetry"
	"github.com/kyma-project/kyma-docs-search/prompts"
)

const (
	rrfK        = 60
	numQueries  = 4
	rerankExtra = 3
	ScoreCosine = "cosine"
	ScoreRRF    = "rrf"
	ScoreLLM    = "llm"
	ScoreBM25   = "bm25"

	ModeDense  = "dense"
	ModeSparse = "sparse"
	ModeHybrid = "hybrid"
)

type Embedder interface {
	Embeddings(ctx context.Context, texts []string) ([][]float32, aicore.Usage, error)
	ChatToolCall(ctx context.Context, model string, messages []aicore.Message, toolSchema map[string]any) (json.RawMessage, aicore.Usage, error)
}

type Pipeline struct {
	Store     store.Store
	AI        Embedder
	MiniModel string
	Sparse    *sparse.Manager
}

type Request struct {
	Query         string
	TopK          int
	ExpandQueries bool
	Rerank        bool
	Modules       []string
	Mode          string // dense (default), sparse, hybrid
}

type Response struct {
	Results   []store.Chunk
	Queries   []string
	ScoreType string
	Run       store.Run
}

var tracer = telemetry.Tracer("kyma-docs-search/pipeline")

func llmAttrs(model string, u aicore.Usage) []attribute.KeyValue {
	return []attribute.KeyValue{
		attribute.String("gen_ai.operation.name", "chat"),
		attribute.String("gen_ai.request.model", model),
		attribute.Int("gen_ai.usage.input_tokens", u.InputTokens),
		attribute.Int("gen_ai.usage.output_tokens", u.OutputTokens),
	}
}

func (p *Pipeline) Search(ctx context.Context, req Request) (resp Response, err error) {
	mode := req.Mode
	if mode == "" {
		mode = ModeDense
	}
	ctx, span := tracer.Start(ctx, "search", trace.WithAttributes(
		attribute.String("mode", mode), attribute.Int("top_k", req.TopK),
		attribute.Bool("expand_queries", req.ExpandQueries), attribute.Bool("rerank", req.Rerank),
		attribute.Int("filter.modules", len(req.Modules))))
	defer func() {
		if err != nil {
			telemetry.Fail(span, err)
		} else {
			span.SetAttributes(attribute.Int("result.count", len(resp.Results)),
				attribute.String("score_type", resp.ScoreType), attribute.String("index.run_id", resp.Run.RunID))
			// With the content switch on: one line per result, "score [module] title", never the chunk text.
			span.SetAttributes(telemetry.ContentStrings("results.summary", resultSummary(resp.Results))...)
		}
		span.End()
	}()
	span.SetAttributes(telemetry.Content("query", req.Query)...)
	span.SetAttributes(telemetry.ContentStrings("filter.modules.list", req.Modules)...)

	run, err := p.Store.Current(ctx)
	if err != nil {
		return Response{}, err
	}

	queries := []string{strings.TrimSpace(req.Query)}
	if req.ExpandQueries {
		extra, err := p.expand(ctx, req.Query)
		if err != nil {
			slog.Warn("query expansion failed, using original query only", "error", err)
		}
		queries = dedupe(append(queries, extra...))
	}

	candidateK := req.TopK
	if len(queries) > 1 || req.Rerank {
		candidateK = max(req.TopK*4, 10)
	}

	var sx *sparse.Index
	if mode != ModeDense {
		if p.Sparse == nil {
			return Response{}, sparse.ErrNotReady
		}
		if sx, err = p.Sparse.Get(ctx); err != nil {
			return Response{}, err
		}
	}

	var vecs [][]float32
	if mode != ModeSparse {
		vecs, err = p.embed(ctx, queries)
		if err != nil {
			return Response{}, fmt.Errorf("embed queries: %w", err)
		}
	}

	lists := make([][]store.Chunk, len(queries))
	errs := make([]error, len(queries))
	var wg sync.WaitGroup
	for i := range queries {
		wg.Add(1)
		go func() {
			defer wg.Done()
			switch mode {
			case ModeSparse:
				lists[i] = p.sparseSearch(ctx, sx, queries[i], candidateK, req.Modules)
			case ModeHybrid:
				var dense []store.Chunk
				dense, errs[i] = p.dense(ctx, run, vecs[i], queries[i], candidateK, req.Modules)
				if errs[i] == nil {
					sp := p.sparseSearch(ctx, sx, queries[i], candidateK, req.Modules)
					lists[i] = fuse(ctx, [][]store.Chunk{sp, dense})
				}
			default:
				lists[i], errs[i] = p.dense(ctx, run, vecs[i], queries[i], candidateK, req.Modules)
			}
		}()
	}
	wg.Wait()
	for _, e := range errs {
		if e != nil {
			return Response{}, fmt.Errorf("dense search: %w", e)
		}
	}

	var results []store.Chunk
	scoreType := ScoreCosine
	switch {
	case len(queries) > 1:
		results = fuse(ctx, lists)
		scoreType = ScoreRRF
	default:
		results = lists[0]
		switch mode {
		case ModeSparse:
			scoreType = ScoreBM25
		case ModeHybrid:
			scoreType = ScoreRRF
		}
	}

	if req.Rerank && len(results) > 0 {
		cands := results[:min(len(results), req.TopK+rerankExtra)]
		reranked, err := p.rerank(ctx, cands, queries)
		if err != nil {
			slog.Warn("rerank failed, keeping previous order", "error", err)
		} else {
			results, scoreType = reranked, ScoreLLM
		}
	}
	if len(results) > req.TopK {
		results = results[:req.TopK]
	}
	if results == nil {
		results = []store.Chunk{}
	}
	return Response{Results: results, Queries: queries, ScoreType: scoreType, Run: run}, nil
}

func dedupe(in []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, q := range in {
		q = strings.TrimSpace(q)
		if q == "" || seen[q] {
			continue
		}
		seen[q] = true
		out = append(out, q)
	}
	return out
}

func (p *Pipeline) expand(ctx context.Context, query string) (out []string, err error) {
	ctx, span := tracer.Start(ctx, "expand_queries")
	defer func() {
		if err != nil {
			telemetry.Fail(span, err)
		} else {
			span.SetAttributes(attribute.Int("queries.generated", len(out)))
			span.SetAttributes(telemetry.ContentStrings("queries.list", out)...)
		}
		span.End()
	}()
	followup := strings.ReplaceAll(prompts.QueryGeneratorFollowup, "{num_queries}", fmt.Sprint(numQueries))
	span.SetAttributes(telemetry.Content("prompt", prompts.QueryGeneratorSystem+"\nOriginal query: "+query)...)
	raw, usage, err := p.AI.ChatToolCall(ctx, p.MiniModel, []aicore.Message{
		{Role: "system", Content: prompts.QueryGeneratorSystem},
		{Role: "user", Content: "Original query: " + query},
		{Role: "system", Content: followup},
	}, map[string]any{
		"name":        "generate_queries",
		"description": "Return the alternative search queries",
		"parameters": map[string]any{
			"type": "object",
			"properties": map[string]any{
				"queries": map[string]any{"type": "array", "items": map[string]any{"type": "string"}},
			},
			"required": []string{"queries"},
		},
	})
	span.SetAttributes(llmAttrs(p.MiniModel, usage)...)
	if err != nil {
		return nil, err
	}
	var dec struct {
		Queries []string `json:"queries"`
	}
	if err := json.Unmarshal(raw, &dec); err != nil {
		return nil, fmt.Errorf("decode queries: %w", err)
	}
	return dec.Queries, nil
}

// RRF merges ranked lists with reciprocal rank fusion, keyed by chunk content.
// The returned Score is the fused score.
func RRF(lists [][]store.Chunk, k float64) []store.Chunk {
	scores := map[string]float64{}
	byKey := map[string]store.Chunk{}
	var order []string
	for _, l := range lists {
		for rank, c := range l {
			if _, ok := byKey[c.Content]; !ok {
				byKey[c.Content] = c
				order = append(order, c.Content)
			}
			scores[c.Content] += 1 / (float64(rank) + k)
		}
	}
	sort.SliceStable(order, func(i, j int) bool { return scores[order[i]] > scores[order[j]] })
	out := make([]store.Chunk, 0, len(order))
	for _, key := range order {
		c := byKey[key]
		c.Score = scores[key]
		out = append(out, c)
	}
	return out
}

func metaString(raw json.RawMessage, keys ...string) string {
	var m map[string]any
	if json.Unmarshal(raw, &m) != nil {
		return ""
	}
	for _, k := range keys {
		if s, ok := m[k].(string); ok && s != "" {
			return s
		}
	}
	return ""
}

func (p *Pipeline) rerank(ctx context.Context, cands []store.Chunk, queries []string) (res []store.Chunk, err error) {
	ctx, span := tracer.Start(ctx, "rerank", trace.WithAttributes(attribute.Int("input.count", len(cands))))
	defer func() {
		if err != nil {
			telemetry.Fail(span, err)
			span.SetAttributes(attribute.Bool("fallback", true))
		} else {
			span.SetAttributes(attribute.Int("output.count", len(res)), attribute.Bool("fallback", false))
		}
		span.End()
	}()
	type doc struct {
		ID      string `json:"id"`
		Title   string `json:"title"`
		URL     string `json:"url"`
		Module  string `json:"module"`
		Content string `json:"page_content"`
	}
	docs := make([]doc, len(cands))
	byID := map[string]store.Chunk{}
	for i, c := range cands {
		id := fmt.Sprintf("doc_%d", i+1)
		docs[i] = doc{id, metaString(c.Metadata, "title"), metaString(c.Metadata, "url", "source"),
			metaString(c.Metadata, "module"), c.Content}
		byID[id] = c
	}
	docsJSON, err := marshalCompact(docs)
	if err != nil {
		return nil, err
	}
	queriesJSON, err := marshalCompact(queries)
	if err != nil {
		return nil, err
	}
	prompt := strings.NewReplacer("{documents}", docsJSON, "{queries}", queriesJSON).Replace(prompts.Reranker)

	span.SetAttributes(telemetry.Content("prompt", prompt)...)
	raw, usage, err := p.AI.ChatToolCall(ctx, p.MiniModel, []aicore.Message{{Role: "user", Content: prompt}}, map[string]any{
		"name":        "rank_documents",
		"description": "Return a relevancy score for each document",
		"parameters": map[string]any{
			"type": "object",
			"properties": map[string]any{
				"documents": map[string]any{
					"type": "array",
					"items": map[string]any{
						"type": "object",
						"properties": map[string]any{
							"id":    map[string]any{"type": "string"},
							"score": map[string]any{"type": "number"},
						},
						"required": []string{"id", "score"},
					},
				},
			},
			"required": []string{"documents"},
		},
	})
	span.SetAttributes(llmAttrs(p.MiniModel, usage)...)
	if err != nil {
		return nil, err
	}
	var out struct {
		Documents []struct {
			ID    string  `json:"id"`
			Score float64 `json:"score"`
		} `json:"documents"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("decode scores: %w", err)
	}
	seen := map[string]bool{}
	for _, d := range out.Documents {
		c, ok := byID[d.ID]
		if !ok || seen[d.ID] {
			continue
		}
		seen[d.ID] = true
		c.Score = d.Score
		res = append(res, c)
	}
	if len(res) == 0 {
		return nil, fmt.Errorf("reranker returned no known document ids")
	}
	sort.SliceStable(res, func(i, j int) bool { return res[i].Score > res[j].Score })
	return res, nil
}

func marshalCompact(v any) (string, error) {
	var sb strings.Builder
	enc := json.NewEncoder(&sb)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return "", err
	}
	return strings.TrimSpace(sb.String()), nil
}

func (p *Pipeline) embed(ctx context.Context, queries []string) ([][]float32, error) {
	ctx, span := tracer.Start(ctx, "embed", trace.WithAttributes(attribute.Int("input.count", len(queries))))
	defer span.End()
	vecs, usage, err := p.AI.Embeddings(ctx, queries)
	if err != nil {
		telemetry.Fail(span, err)
		return nil, err
	}
	span.SetAttributes(attribute.Int("dimensions", len(vecs[0])))
	if usage.InputTokens > 0 {
		span.SetAttributes(attribute.Int("gen_ai.usage.input_tokens", usage.InputTokens))
	}
	return vecs, nil
}

func (p *Pipeline) dense(ctx context.Context, run store.Run, vec []float32, query string, k int, modules []string) ([]store.Chunk, error) {
	ctx, span := tracer.Start(ctx, "dense", trace.WithAttributes(attribute.Int("k", k), attribute.Bool("filtered", len(modules) > 0)))
	defer span.End()
	span.SetAttributes(telemetry.Content("query", query)...)
	hits, err := p.Store.Dense(ctx, run, vec, k, modules)
	if err != nil {
		telemetry.Fail(span, err)
		return nil, err
	}
	span.SetAttributes(attribute.Int("hits", len(hits)))
	return hits, nil
}

func (p *Pipeline) sparseSearch(ctx context.Context, sx *sparse.Index, query string, k int, modules []string) []store.Chunk {
	_, span := tracer.Start(ctx, "sparse", trace.WithAttributes(attribute.Int("k", k), attribute.String("index.run_id", sx.RunID)))
	defer span.End()
	span.SetAttributes(telemetry.Content("query", query)...)
	hits := sx.Search(query, k, modules)
	span.SetAttributes(attribute.Int("hits", len(hits)))
	return hits
}

func fuse(ctx context.Context, lists [][]store.Chunk) []store.Chunk {
	_, span := tracer.Start(ctx, "fuse", trace.WithAttributes(attribute.Int("inputs", len(lists))))
	defer span.End()
	out := RRF(lists, rrfK)
	span.SetAttributes(attribute.Int("candidates", len(out)))
	return out
}

// resultSummary renders results as "score [module] title" lines for span attributes.
func resultSummary(results []store.Chunk) []string {
	out := make([]string, 0, len(results))
	for _, c := range results {
		var m struct{ Module, Title string }
		_ = json.Unmarshal(c.Metadata, &struct {
			Module *string `json:"module"`
			Title  *string `json:"title"`
		}{&m.Module, &m.Title})
		out = append(out, fmt.Sprintf("%.3f [%s] %s", c.Score, m.Module, m.Title))
	}
	return out
}
