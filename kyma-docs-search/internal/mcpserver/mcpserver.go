// Package mcpserver exposes the search pipeline as an MCP server (streamable HTTP).
// It contains no retrieval logic: a tool call is mapped to the same in-process
// pipeline call that POST /v1/search uses.
package mcpserver

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/kyma-project/kyma-docs-search/internal/pipeline"
)

const toolDescription = "Semantic and keyword search over Kyma documentation (kyma-project repositories and the SAP BTP Kyma runtime docs). " +
	"Use it to answer questions about Kyma concepts, modules, setup and usage. Returns the most relevant passages, " +
	"each with title, content, source_url, score and module. Always cite the source_url in your answer."

// SearchInput is the tool input.
type SearchInput struct {
	Query         string `json:"query" jsonschema:"natural-language question to search the Kyma docs for"`
	TopK          int    `json:"top_k,omitempty" jsonschema:"maximum number of passages to return, 1-50 (default 5)"`
	Mode          string `json:"mode,omitempty" jsonschema:"retrieval mode: dense, sparse or hybrid (default hybrid)"`
	ExpandQueries bool   `json:"expand_queries,omitempty" jsonschema:"let an LLM expand the query into variants (default false)"`
	Rerank        bool   `json:"rerank,omitempty" jsonschema:"let an LLM rerank the candidates (default false)"`
}

// Hit is one passage.
type Hit struct {
	Title     string  `json:"title"`
	Content   string  `json:"content"`
	SourceURL string  `json:"source_url"`
	Score     float64 `json:"score"`
	Module    string  `json:"module"`
}

// SearchOutput is the structured tool result (MCP requires an object at the top level).
type SearchOutput struct {
	Results []Hit `json:"results"`
}

// Handler returns the http.Handler to mount at /mcp.
func Handler(p *pipeline.Pipeline) http.Handler {
	s := mcp.NewServer(&mcp.Implementation{Name: "kyma-docs-search", Version: "0.1.0"}, nil)
	mcp.AddTool(s, &mcp.Tool{Name: "search_kyma_docs", Description: toolDescription},
		func(ctx context.Context, _ *mcp.CallToolRequest, in SearchInput) (*mcp.CallToolResult, SearchOutput, error) {
			out, err := search(ctx, p, in)
			if err != nil {
				return &mcp.CallToolResult{IsError: true, Content: []mcp.Content{&mcp.TextContent{Text: err.Error()}}}, SearchOutput{}, nil
			}
			b, _ := json.Marshal(out)
			return &mcp.CallToolResult{Content: []mcp.Content{&mcp.TextContent{Text: string(b)}}}, out, nil
		})
	return mcp.NewStreamableHTTPHandler(func(*http.Request) *mcp.Server { return s }, nil)
}

func search(ctx context.Context, p *pipeline.Pipeline, in SearchInput) (SearchOutput, error) {
	if l := len([]rune(in.Query)); l < 1 || l > 4000 {
		return SearchOutput{}, fmt.Errorf("query must be 1-4000 characters")
	}
	if in.TopK == 0 {
		in.TopK = 5
	}
	if in.TopK < 1 || in.TopK > 50 {
		return SearchOutput{}, fmt.Errorf("top_k must be between 1 and 50")
	}
	switch in.Mode {
	case "":
		in.Mode = pipeline.ModeHybrid
	case pipeline.ModeDense, pipeline.ModeSparse, pipeline.ModeHybrid:
	default:
		return SearchOutput{}, fmt.Errorf("mode must be one of dense, sparse, hybrid")
	}
	res, err := p.Search(ctx, pipeline.Request{Query: in.Query, TopK: in.TopK, ExpandQueries: in.ExpandQueries, Rerank: in.Rerank, Mode: in.Mode})
	if err != nil {
		return SearchOutput{}, fmt.Errorf("search failed: %w", err)
	}
	out := SearchOutput{Results: make([]Hit, 0, len(res.Results))}
	for _, c := range res.Results {
		var m struct{ URL, Title, Module string }
		var raw map[string]any
		if json.Unmarshal(c.Metadata, &raw) == nil {
			m.URL, _ = raw["url"].(string)
			m.Title, _ = raw["title"].(string)
			m.Module, _ = raw["module"].(string)
		}
		out.Results = append(out.Results, Hit{Title: m.Title, Content: c.Content, SourceURL: m.URL, Score: c.Score, Module: m.Module})
	}
	return out, nil
}
