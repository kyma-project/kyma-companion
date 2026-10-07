// Package api contains the HTTP handlers.
package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"github.com/kyma-project/kyma-docs-search/internal/mcpserver"
	"github.com/kyma-project/kyma-docs-search/internal/pipeline"
	"github.com/kyma-project/kyma-docs-search/internal/sparse"
	"github.com/kyma-project/kyma-docs-search/internal/store"
)

type Server struct {
	Pipeline       *pipeline.Pipeline
	Store          store.Store
	EmbeddingModel string
	Dimensions     int // expected embedding dimensions, determined at startup
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/search", s.search)
	mux.HandleFunc("GET /v1/status", s.status)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) { writeJSON(w, 200, map[string]string{"status": "ok"}) })
	mux.HandleFunc("GET /readyz", s.readyz)
	// Second door on the same pipeline; see internal/mcpserver.
	mux.Handle("/mcp", mcpserver.Handler(s.Pipeline))
	return logMiddleware(mux)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

type statusWriter struct {
	http.ResponseWriter
	code int
}

func (w *statusWriter) WriteHeader(c int) { w.code = c; w.ResponseWriter.WriteHeader(c) }

// Unwrap lets http.ResponseController reach Flush on the real writer (needed for MCP streaming).
func (w *statusWriter) Unwrap() http.ResponseWriter { return w.ResponseWriter }

func (w *statusWriter) Flush() {
	if f, ok := w.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func logMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		sw := &statusWriter{ResponseWriter: w, code: 200}
		next.ServeHTTP(sw, r)
		slog.Info("request", "method", r.Method, "path", r.URL.Path, "status", sw.code, "duration_ms", time.Since(start).Milliseconds())
	})
}

type searchRequest struct {
	Query         string `json:"query"`
	TopK          *int   `json:"top_k"`
	ExpandQueries bool   `json:"expand_queries"`
	Rerank        bool   `json:"rerank"`
	Mode          string `json:"mode"`
	Filters       *struct {
		Module []string `json:"module"`
	} `json:"filters"`
}

func (s *Server) search(w http.ResponseWriter, r *http.Request) {
	var in searchRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&in); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON body: "+err.Error())
		return
	}
	if l := len([]rune(in.Query)); l < 1 || l > 4000 {
		writeErr(w, http.StatusBadRequest, "query must be 1-4000 characters")
		return
	}
	topK := 5
	if in.TopK != nil {
		topK = *in.TopK
	}
	if topK < 1 || topK > 50 {
		writeErr(w, http.StatusBadRequest, "top_k must be between 1 and 50")
		return
	}
	switch in.Mode {
	case "", pipeline.ModeDense, pipeline.ModeSparse, pipeline.ModeHybrid:
	default:
		writeErr(w, http.StatusBadRequest, "mode must be one of dense, sparse, hybrid")
		return
	}
	req := pipeline.Request{Query: in.Query, TopK: topK, ExpandQueries: in.ExpandQueries, Rerank: in.Rerank, Mode: in.Mode}
	if in.Filters != nil {
		req.Modules = in.Filters.Module
	}

	res, err := s.Pipeline.Search(r.Context(), req)
	if err != nil {
		slog.Error("search failed", "error", err)
		if errors.Is(err, store.ErrNoRun) {
			writeErr(w, http.StatusServiceUnavailable, "no committed index")
			return
		}
		if errors.Is(err, sparse.ErrNotReady) {
			writeErr(w, http.StatusServiceUnavailable, "sparse index is still being built, retry shortly or use mode=dense")
			return
		}
		writeErr(w, http.StatusServiceUnavailable, "upstream unavailable: "+err.Error())
		return
	}
	idx := map[string]any{"run_id": res.Run.RunID, "embedding_model": res.Run.EmbeddingModel}
	if res.Run.CommittedAt != nil {
		idx["committed_at"] = res.Run.CommittedAt
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"results": res.Results, "queries": res.Queries, "score_type": res.ScoreType, "index": idx,
	})
}

func (s *Server) status(w http.ResponseWriter, r *http.Request) {
	run, err := s.Store.Current(r.Context())
	if err != nil {
		if errors.Is(err, store.ErrNoRun) {
			writeErr(w, http.StatusServiceUnavailable, "no committed index")
			return
		}
		writeErr(w, http.StatusServiceUnavailable, "database unavailable")
		return
	}
	writeJSON(w, http.StatusOK, run)
}

// Ready checks db, current run, and model/dimension match.
func (s *Server) Ready(ctx context.Context) error {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	if err := s.Store.Ping(ctx); err != nil {
		return fmt.Errorf("database unreachable: %w", err)
	}
	run, err := s.Store.Current(ctx)
	if err != nil {
		return err
	}
	if run.EmbeddingModel != s.EmbeddingModel {
		return fmt.Errorf("index embedding model %q differs from configured %q", run.EmbeddingModel, s.EmbeddingModel)
	}
	if run.Dimensions != s.Dimensions {
		return fmt.Errorf("index dimensions %d differ from model dimensions %d", run.Dimensions, s.Dimensions)
	}
	return nil
}

func (s *Server) readyz(w http.ResponseWriter, r *http.Request) {
	if err := s.Ready(r.Context()); err != nil {
		writeErr(w, http.StatusServiceUnavailable, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}
