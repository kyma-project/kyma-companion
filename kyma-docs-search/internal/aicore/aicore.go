// Package aicore is a minimal SAP AI Core client: OAuth, deployment lookup, embeddings, chat tool calls.
package aicore

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

const apiVersion = "2025-03-01-preview"

type Client struct {
	authURL, baseURL, clientID, clientSecret, resourceGroup string
	deployments                                             map[string]string // model -> deployment id
	embeddingModel                                          string
	http                                                    *http.Client

	mu       sync.Mutex
	token    string
	tokenExp time.Time
	urls     map[string]string // deployment id -> url
}

func New(authURL, baseURL, clientID, clientSecret, resourceGroup, embeddingModel string, deployments map[string]string) *Client {
	return &Client{
		authURL: authURL, baseURL: strings.TrimRight(baseURL, "/"), clientID: clientID,
		clientSecret: clientSecret, resourceGroup: resourceGroup, embeddingModel: embeddingModel,
		deployments: deployments, http: &http.Client{Timeout: 30 * time.Second}, urls: map[string]string{},
	}
}

func (c *Client) getToken(ctx context.Context) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	// Round(0) strips the monotonic clock reading: on a sleeping laptop the monotonic clock
	// stands still while the token's wall-clock expiry passes, so compare wall clock only.
	if c.token != "" && time.Now().Round(0).Before(c.tokenExp) {
		return c.token, nil
	}
	form := url.Values{"grant_type": {"client_credentials"}}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.authURL, strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.SetBasicAuth(c.clientID, c.clientSecret)
	body, status, err := c.do(req)
	if err != nil {
		return "", fmt.Errorf("token request: %w", err)
	}
	if status != http.StatusOK {
		return "", fmt.Errorf("token endpoint returned %d", status)
	}
	var tr struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int    `json:"expires_in"`
	}
	if err := json.Unmarshal(body, &tr); err != nil || tr.AccessToken == "" {
		return "", errors.New("token endpoint: bad response")
	}
	c.token = tr.AccessToken
	c.tokenExp = time.Now().Round(0).Add(time.Duration(tr.ExpiresIn-60) * time.Second)
	return c.token, nil
}

// invalidateToken drops the cached token so the next call fetches a fresh one.
func (c *Client) invalidateToken() {
	c.mu.Lock()
	c.token = ""
	c.mu.Unlock()
}

func (c *Client) do(req *http.Request) ([]byte, int, error) {
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	b, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	return b, resp.StatusCode, err
}

func (c *Client) deploymentURL(ctx context.Context, token, id string) (string, error) {
	c.mu.Lock()
	u := c.urls[id]
	c.mu.Unlock()
	if u != "" {
		return u, nil
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/lm/deployments/"+id, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("AI-Resource-Group", c.resourceGroup)
	body, status, err := c.do(req)
	if err != nil {
		return "", fmt.Errorf("deployment lookup: %w", err)
	}
	if status != http.StatusOK {
		return "", fmt.Errorf("deployment lookup %d: %s", status, trunc(body))
	}
	var d struct {
		DeploymentURL string `json:"deploymentUrl"`
	}
	if err := json.Unmarshal(body, &d); err != nil || d.DeploymentURL == "" {
		return "", fmt.Errorf("deployment %s has no deploymentUrl", id)
	}
	c.mu.Lock()
	c.urls[id] = d.DeploymentURL
	c.mu.Unlock()
	return d.DeploymentURL, nil
}

func trunc(b []byte) string {
	if len(b) > 300 {
		b = b[:300]
	}
	return string(b)
}

// post sends a JSON body to {deploymentUrl}/{path}?api-version=... for the given model.
func (c *Client) post(ctx context.Context, model, path string, payload any) ([]byte, error) {
	return c.postOnce(ctx, model, path, payload, false)
}

func (c *Client) postOnce(ctx context.Context, model, path string, payload any, retried bool) ([]byte, error) {
	id := c.deployments[model]
	if id == "" {
		return nil, fmt.Errorf("no deployment configured for model %q", model)
	}
	token, err := c.getToken(ctx)
	if err != nil {
		return nil, err
	}
	base, err := c.deploymentURL(ctx, token, id)
	if err != nil {
		return nil, err
	}
	b, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		strings.TrimRight(base, "/")+path+"?api-version="+apiVersion, bytes.NewReader(b))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("AI-Resource-Group", c.resourceGroup)
	body, status, err := c.do(req)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	if status == http.StatusUnauthorized && !retried {
		// The cached token was rejected (expired, or the client secret was rotated): fetch a new one and retry once.
		c.invalidateToken()
		return c.postOnce(ctx, model, path, payload, true)
	}
	if status != http.StatusOK {
		return nil, fmt.Errorf("%s returned %d: %s", path, status, trunc(body))
	}
	return body, nil
}

// Embeddings embeds all texts in one call using the configured embedding model.
func (c *Client) Embeddings(ctx context.Context, texts []string) ([][]float32, error) {
	body, err := c.post(ctx, c.embeddingModel, "/embeddings", map[string]any{"input": texts})
	if err != nil {
		return nil, err
	}
	var r struct {
		Data []struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &r); err != nil {
		return nil, fmt.Errorf("embeddings decode: %w", err)
	}
	if len(r.Data) != len(texts) {
		return nil, fmt.Errorf("embeddings: got %d vectors for %d inputs", len(r.Data), len(texts))
	}
	out := make([][]float32, len(texts))
	for _, d := range r.Data {
		if d.Index < 0 || d.Index >= len(out) {
			return nil, errors.New("embeddings: bad index")
		}
		out[d.Index] = d.Embedding
	}
	return out, nil
}

// Message is a chat message.
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ChatToolCall forces a call of one function tool and returns its JSON arguments.
// toolSchema is {"name":..., "description":..., "parameters": {...}} (the OpenAI function object).
func (c *Client) ChatToolCall(ctx context.Context, model string, messages []Message, toolSchema map[string]any) (json.RawMessage, error) {
	name, _ := toolSchema["name"].(string)
	body, err := c.post(ctx, model, "/chat/completions", map[string]any{
		"messages":    messages,
		"tools":       []any{map[string]any{"type": "function", "function": toolSchema}},
		"tool_choice": map[string]any{"type": "function", "function": map[string]any{"name": name}},
	})
	if err != nil {
		return nil, err
	}
	var r struct {
		Choices []struct {
			Message struct {
				ToolCalls []struct {
					Function struct {
						Arguments string `json:"arguments"`
					} `json:"function"`
				} `json:"tool_calls"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.Unmarshal(body, &r); err != nil {
		return nil, fmt.Errorf("chat decode: %w", err)
	}
	if len(r.Choices) == 0 || len(r.Choices[0].Message.ToolCalls) == 0 {
		return nil, errors.New("chat: no tool call in response")
	}
	return json.RawMessage(r.Choices[0].Message.ToolCalls[0].Function.Arguments), nil
}
