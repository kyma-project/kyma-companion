// Package store reads the pgvector index written by the indexer. It never writes.
package store

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// ErrNoRun means no committed (current) index run exists.
var ErrNoRun = errors.New("no current index run")

type Run struct {
	RunID          string                     `json:"run_id"`
	TableName      string                     `json:"table_name"`
	EmbeddingModel string                     `json:"embedding_model"`
	Dimensions     int                        `json:"dimensions"`
	ChunkCount     int                        `json:"chunk_count"`
	Sources        map[string]json.RawMessage `json:"sources"`
	CreatedAt      time.Time                  `json:"created_at"`
	CommittedAt    *time.Time                 `json:"committed_at"`
}

type Chunk struct {
	Content  string          `json:"content"`
	Score    float64         `json:"score"`
	Metadata json.RawMessage `json:"metadata"`
}

// ChunkRef is a chunk without its embedding, used to build the in-memory sparse index.
type ChunkRef struct {
	ID       int64
	Content  string
	Metadata json.RawMessage
}

type Store interface {
	AllChunks(ctx context.Context, run Run) ([]ChunkRef, error)
	Current(ctx context.Context) (Run, error)
	Dense(ctx context.Context, run Run, vector []float32, k int, moduleFilter []string) ([]Chunk, error)
	Ping(ctx context.Context) error
}

type PG struct {
	pool *pgxpool.Pool

	mu      sync.Mutex
	cached  Run
	cachedT time.Time
}

const cacheTTL = 30 * time.Second

func NewPG(ctx context.Context, dsn string) (*PG, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, err
	}
	return &PG{pool: pool}, nil
}

func (p *PG) Close() { p.pool.Close() }

func (p *PG) Ping(ctx context.Context) error { return p.pool.Ping(ctx) }

func (p *PG) Current(ctx context.Context) (Run, error) {
	p.mu.Lock()
	if p.cached.RunID != "" && time.Since(p.cachedT) < cacheTTL {
		r := p.cached
		p.mu.Unlock()
		return r, nil
	}
	p.mu.Unlock()

	var r Run
	var sources []byte
	err := p.pool.QueryRow(ctx, `SELECT run_id, table_name, embedding_model, dimensions, chunk_count,
		sources, created_at, committed_at FROM docs_index_runs WHERE is_current`).
		Scan(&r.RunID, &r.TableName, &r.EmbeddingModel, &r.Dimensions, &r.ChunkCount, &sources, &r.CreatedAt, &r.CommittedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return Run{}, ErrNoRun
	}
	if err != nil {
		return Run{}, err
	}
	if err := json.Unmarshal(sources, &r.Sources); err != nil {
		r.Sources = map[string]json.RawMessage{}
	}
	p.mu.Lock()
	p.cached, p.cachedT = r, time.Now()
	p.mu.Unlock()
	return r, nil
}

var identRe = regexp.MustCompile(`^[a-z0-9_]+$`)

func vectorLiteral(v []float32) string {
	var sb strings.Builder
	sb.WriteByte('[')
	for i, f := range v {
		if i > 0 {
			sb.WriteByte(',')
		}
		sb.WriteString(strconv.FormatFloat(float64(f), 'g', -1, 32))
	}
	sb.WriteByte(']')
	return sb.String()
}

func (p *PG) Dense(ctx context.Context, run Run, vector []float32, k int, moduleFilter []string) ([]Chunk, error) {
	if !identRe.MatchString(run.TableName) {
		return nil, fmt.Errorf("invalid table name %q", run.TableName)
	}
	where := ""
	args := []any{vectorLiteral(vector), k}
	if len(moduleFilter) > 0 {
		where = "WHERE metadata->>'module' = ANY($3)"
		args = append(args, moduleFilter)
	}
	q := fmt.Sprintf(`SELECT content, metadata, 1 - (embedding <=> $1::vector) AS score
		FROM %s %s ORDER BY embedding <=> $1::vector LIMIT $2`, run.TableName, where)
	rows, err := p.pool.Query(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Chunk
	for rows.Next() {
		var c Chunk
		var meta []byte
		if err := rows.Scan(&c.Content, &meta, &c.Score); err != nil {
			return nil, err
		}
		c.Metadata = json.RawMessage(meta)
		out = append(out, c)
	}
	return out, rows.Err()
}

// AllChunks streams id, content and metadata of every chunk of the run (no embeddings).
func (p *PG) AllChunks(ctx context.Context, run Run) ([]ChunkRef, error) {
	if !identRe.MatchString(run.TableName) {
		return nil, fmt.Errorf("invalid table name %q", run.TableName)
	}
	rows, err := p.pool.Query(ctx, fmt.Sprintf(`SELECT id, content, metadata FROM %s ORDER BY id`, run.TableName))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]ChunkRef, 0, max(run.ChunkCount, 0))
	for rows.Next() {
		var c ChunkRef
		var meta []byte
		if err := rows.Scan(&c.ID, &c.Content, &meta); err != nil {
			return nil, err
		}
		c.Metadata = json.RawMessage(meta)
		out = append(out, c)
	}
	return out, rows.Err()
}
