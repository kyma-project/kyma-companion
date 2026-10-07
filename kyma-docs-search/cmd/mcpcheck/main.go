// Command mcpcheck connects to an MCP server URL, lists tools and calls search_kyma_docs.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: mcpcheck <mcp-url>")
		os.Exit(2)
	}
	if err := run(os.Args[1]); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func run(url string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	client := mcp.NewClient(&mcp.Implementation{Name: "mcpcheck", Version: "0.1.0"}, nil)
	cs, err := client.Connect(ctx, &mcp.StreamableClientTransport{Endpoint: url}, nil)
	if err != nil {
		return err
	}
	defer cs.Close()
	tools, err := cs.ListTools(ctx, nil)
	if err != nil {
		return err
	}
	for _, t := range tools.Tools {
		fmt.Printf("tool: %s\n  %s\n", t.Name, t.Description)
	}
	res, err := cs.CallTool(ctx, &mcp.CallToolParams{Name: "search_kyma_docs",
		Arguments: map[string]any{"query": "kyma alpha module add", "top_k": 3, "mode": "hybrid"}})
	if err != nil {
		return err
	}
	fmt.Println("isError:", res.IsError, "text content blocks:", len(res.Content))
	b, _ := json.Marshal(res.StructuredContent)
	var out struct {
		Results []struct {
			Title, Module, SourceURL string  `json:"-"`
			T                        string  `json:"title"`
			M                        string  `json:"module"`
			U                        string  `json:"source_url"`
			S                        float64 `json:"score"`
		} `json:"results"`
	}
	if err := json.Unmarshal(b, &out); err != nil {
		return err
	}
	for i, r := range out.Results {
		fmt.Printf("%d. %s\n   module=%s score=%.4f\n   %s\n", i+1, r.T, r.M, r.S, r.U)
	}
	return nil
}
