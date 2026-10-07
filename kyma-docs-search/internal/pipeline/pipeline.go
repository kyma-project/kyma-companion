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

	"github.com/kyma-project/kyma-docs-search/internal/aicore"
	"github.com/kyma-project/kyma-docs-search/internal/sparse"
	"github.com/kyma-project/kyma-docs-search/internal/store"
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
	Embeddings(ctx context.Context, texts []string) ([][]float32, error)
	ChatToolCall(ctx context.Context, model string, messages []aicore.Message, toolSchema map[string]any) (json.RawMessage, error)
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

func (p *Pipeline) Search(ctx context.Context, req Request) (Response, error) {
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

	mode := req.Mode
	if mode == "" {
		mode = ModeDense
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
		vecs, err = p.AI.Embeddings(ctx, queries)
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
				lists[i] = sx.Search(queries[i], candidateK, req.Modules)
			case ModeHybrid:
				var dense []store.Chunk
				dense, errs[i] = p.Store.Dense(ctx, run, vecs[i], candidateK, req.Modules)
				if errs[i] == nil {
					lists[i] = RRF([][]store.Chunk{sx.Search(queries[i], candidateK, req.Modules), dense}, rrfK)
				}
			default:
				lists[i], errs[i] = p.Store.Dense(ctx, run, vecs[i], candidateK, req.Modules)
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
		results = RRF(lists, rrfK)
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

func (p *Pipeline) expand(ctx context.Context, query string) ([]string, error) {
	followup := strings.ReplaceAll(prompts.QueryGeneratorFollowup, "{num_queries}", fmt.Sprint(numQueries))
	raw, err := p.AI.ChatToolCall(ctx, p.MiniModel, []aicore.Message{
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
	if err != nil {
		return nil, err
	}
	var out struct {
		Queries []string `json:"queries"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("decode queries: %w", err)
	}
	return out.Queries, nil
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

func (p *Pipeline) rerank(ctx context.Context, cands []store.Chunk, queries []string) ([]store.Chunk, error) {
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

	raw, err := p.AI.ChatToolCall(ctx, p.MiniModel, []aicore.Message{{Role: "user", Content: prompt}}, map[string]any{
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
	var res []store.Chunk
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
