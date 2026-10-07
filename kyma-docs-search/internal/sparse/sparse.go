// Package sparse implements an in-memory BM25 index over the chunks of one index run.
// It is independent of the store: chunks are loaded once through a Loader and kept in memory.
package sparse

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"math"
	"sort"
	"sync/atomic"
	"time"
	"unicode"

	"github.com/kyma-project/kyma-docs-search/internal/store"
)

const (
	k1 = 1.2
	b  = 0.75
)

// ErrNotReady means the index for the current run has not been built yet.
var ErrNotReady = errors.New("sparse index not ready")

// Tokenize lowercases, splits on characters that are not letters, digits, '-', '_' or '.',
// trims trailing '.' and '-' (sentence punctuation) and drops tokens shorter than 2 chars.
func Tokenize(s string) []string {
	var out []string
	var cur []rune
	flush := func() {
		for len(cur) > 0 && (cur[len(cur)-1] == '.' || cur[len(cur)-1] == '-') {
			cur = cur[:len(cur)-1]
		}
		if len(cur) >= 2 {
			out = append(out, string(cur))
		}
		cur = cur[:0]
	}
	for _, r := range s {
		if unicode.IsLetter(r) || unicode.IsDigit(r) || r == '-' || r == '_' || r == '.' {
			cur = append(cur, unicode.ToLower(r))
		} else {
			flush()
		}
	}
	flush()
	return out
}

type posting struct {
	doc int32
	tf  int32
}

type doc struct {
	content  string
	metadata json.RawMessage
	module   string
	length   int32
}

// Index is immutable after Build.
type Index struct {
	RunID    string
	docs     []doc
	postings map[string][]posting
	avgLen   float64
}

// Build creates an index from chunk refs.
func Build(runID string, chunks []store.ChunkRef) *Index {
	ix := &Index{RunID: runID, docs: make([]doc, len(chunks)), postings: map[string][]posting{}}
	var total int64
	for i, c := range chunks {
		toks := Tokenize(c.Content)
		var meta struct {
			Module string `json:"module"`
		}
		_ = json.Unmarshal(c.Metadata, &meta)
		ix.docs[i] = doc{content: c.Content, metadata: c.Metadata, module: meta.Module, length: int32(len(toks))}
		total += int64(len(toks))
		tf := map[string]int32{}
		for _, t := range toks {
			tf[t]++
		}
		for t, n := range tf {
			ix.postings[t] = append(ix.postings[t], posting{int32(i), n})
		}
	}
	if len(chunks) > 0 {
		ix.avgLen = float64(total) / float64(len(chunks))
	}
	return ix
}

func (ix *Index) Len() int { return len(ix.docs) }

// Search returns the top-k chunks by BM25 score (Score = BM25), restricted to modules if non-empty.
func (ix *Index) Search(query string, k int, modules []string) []store.Chunk {
	var allowed map[string]bool
	if len(modules) > 0 {
		allowed = make(map[string]bool, len(modules))
		for _, m := range modules {
			allowed[m] = true
		}
	}
	n := float64(len(ix.docs))
	scores := map[int32]float64{}
	seen := map[string]bool{}
	for _, t := range Tokenize(query) {
		if seen[t] {
			continue
		}
		seen[t] = true
		ps := ix.postings[t]
		if len(ps) == 0 {
			continue
		}
		df := float64(len(ps))
		idf := math.Log(1 + (n-df+0.5)/(df+0.5))
		for _, p := range ps {
			d := &ix.docs[p.doc]
			if allowed != nil && !allowed[d.module] {
				continue
			}
			tf := float64(p.tf)
			scores[p.doc] += idf * tf * (k1 + 1) / (tf + k1*(1-b+b*float64(d.length)/ix.avgLen))
		}
	}
	ids := make([]int32, 0, len(scores))
	for id := range scores {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool {
		if scores[ids[i]] != scores[ids[j]] {
			return scores[ids[i]] > scores[ids[j]]
		}
		return ids[i] < ids[j]
	})
	if len(ids) > k {
		ids = ids[:k]
	}
	out := make([]store.Chunk, len(ids))
	for i, id := range ids {
		d := ix.docs[id]
		out[i] = store.Chunk{Content: d.content, Score: scores[id], Metadata: d.metadata}
	}
	return out
}

// Loader is the part of the store the manager needs.
type Loader interface {
	Current(ctx context.Context) (store.Run, error)
	AllChunks(ctx context.Context, run store.Run) ([]store.ChunkRef, error)
}

// Manager keeps the index of the current run and rebuilds it in the background on a run change.
type Manager struct {
	Loader Loader

	ptr      atomic.Pointer[Index]
	building atomic.Bool
}

// Start builds the index for the current run in the background and re-checks periodically,
// so a run change is picked up even without sparse requests.
func (m *Manager) Start(ctx context.Context) {
	m.check(ctx)
	go func() {
		t := time.NewTicker(30 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				m.check(ctx)
			}
		}
	}()
}

// check starts a background rebuild if the current run differs from the indexed one.
func (m *Manager) check(ctx context.Context) {
	run, err := m.Loader.Current(ctx)
	if err != nil {
		return
	}
	if cur := m.ptr.Load(); cur != nil && cur.RunID == run.RunID {
		return
	}
	if !m.building.CompareAndSwap(false, true) {
		return
	}
	go func() {
		defer m.building.Store(false)
		start := time.Now()
		chunks, err := m.Loader.AllChunks(ctx, run)
		if err != nil {
			slog.Error("sparse index load failed", "run_id", run.RunID, "error", err)
			return
		}
		ix := Build(run.RunID, chunks)
		m.ptr.Store(ix)
		slog.Info("sparse index built", "run_id", run.RunID, "chunks", ix.Len(), "terms", len(ix.postings),
			"duration_ms", time.Since(start).Milliseconds())
	}()
}

// Get returns the ready index (possibly of the previous run while a rebuild runs) or ErrNotReady.
func (m *Manager) Get(ctx context.Context) (*Index, error) {
	m.check(ctx) // cheap: Current() is cached for 30 s
	if ix := m.ptr.Load(); ix != nil {
		return ix, nil
	}
	return nil, ErrNotReady
}
