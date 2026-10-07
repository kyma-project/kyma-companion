package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/kyma-project/kyma-docs-search/internal/aicore"
	"github.com/kyma-project/kyma-docs-search/internal/api"
	"github.com/kyma-project/kyma-docs-search/internal/config"
	"github.com/kyma-project/kyma-docs-search/internal/pipeline"
	"github.com/kyma-project/kyma-docs-search/internal/sparse"
	"github.com/kyma-project/kyma-docs-search/internal/store"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	if err := run(); err != nil {
		slog.Error("fatal", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	pg, err := store.NewPG(ctx, cfg.PGDSN)
	if err != nil {
		return err
	}
	defer pg.Close()

	ai := aicore.New(cfg.AICoreAuthURL, cfg.AICoreBaseURL, cfg.AICoreClientID, cfg.AICoreClientSecret,
		cfg.AICoreResourceGroup, cfg.EmbeddingModel, cfg.Deployments)

	// Determine the embedding dimensions of the configured model.
	probeCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	vecs, err := ai.Embeddings(probeCtx, []string{"dimension probe"})
	cancel()
	if err != nil {
		return err
	}
	dims := len(vecs[0])
	slog.Info("embedding model probed", "model", cfg.EmbeddingModel, "dimensions", dims)

	sp := &sparse.Manager{Loader: pg}
	sp.Start(ctx) // builds in the background; readiness does not depend on it

	srv := &api.Server{
		Pipeline:       &pipeline.Pipeline{Store: pg, AI: ai, MiniModel: cfg.MiniModel, Sparse: sp},
		Store:          pg,
		EmbeddingModel: cfg.EmbeddingModel,
		Dimensions:     dims,
	}
	if err := srv.Ready(ctx); err != nil {
		slog.Warn("not ready at startup (will keep serving 503 on /readyz)", "reason", err.Error())
	}

	hs := &http.Server{Addr: ":" + cfg.Port, Handler: srv.Routes(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		<-ctx.Done()
		sctx, c := context.WithTimeout(context.Background(), 10*time.Second)
		defer c()
		_ = hs.Shutdown(sctx)
	}()
	slog.Info("listening", "addr", hs.Addr)
	if err := hs.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}
