// Package config loads the service configuration.
package config

import (
	"encoding/json"
	"fmt"
	"os"
)

type Config struct {
	AICoreAuthURL       string
	AICoreBaseURL       string
	AICoreClientID      string
	AICoreClientSecret  string
	AICoreResourceGroup string

	EmbeddingModel string
	MiniModel      string
	// Deployments maps model name to AI Core deployment id.
	Deployments map[string]string

	PGDSN string
	Port  string
}

type file struct {
	AuthURL       string `json:"AICORE_AUTH_URL"`
	BaseURL       string `json:"AICORE_BASE_URL"`
	ClientID      string `json:"AICORE_CLIENT_ID"`
	ClientSecret  string `json:"AICORE_CLIENT_SECRET"`
	ResourceGroup string `json:"AICORE_RESOURCE_GROUP"`
	EmbeddingName string `json:"MAIN_EMBEDDING_MODEL_NAME"`
	MiniName      string `json:"MAIN_MODEL_MINI_NAME"`
	PGDSN         string `json:"DOCS_SEARCH_PG_DSN"`
	Port          string `json:"DOCS_SEARCH_PORT"`
	Models        []struct {
		Name         string `json:"name"`
		DeploymentID string `json:"deployment_id"`
	} `json:"models"`
}

func env(name, fallback string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return fallback
}

// Load reads CONFIG_PATH (kyma-companion config.json format); env vars override file values.
func Load() (Config, error) {
	var f file
	if p := os.Getenv("CONFIG_PATH"); p != "" {
		b, err := os.ReadFile(p)
		if err != nil {
			return Config{}, fmt.Errorf("read config: %w", err)
		}
		if err := json.Unmarshal(b, &f); err != nil {
			return Config{}, fmt.Errorf("parse config: %w", err)
		}
	}
	c := Config{
		AICoreAuthURL:       env("AICORE_AUTH_URL", f.AuthURL),
		AICoreBaseURL:       env("AICORE_BASE_URL", f.BaseURL),
		AICoreClientID:      env("AICORE_CLIENT_ID", f.ClientID),
		AICoreClientSecret:  env("AICORE_CLIENT_SECRET", f.ClientSecret),
		AICoreResourceGroup: env("AICORE_RESOURCE_GROUP", f.ResourceGroup),
		EmbeddingModel:      env("MAIN_EMBEDDING_MODEL_NAME", f.EmbeddingName),
		MiniModel:           env("MAIN_MODEL_MINI_NAME", f.MiniName),
		PGDSN:               env("DOCS_SEARCH_PG_DSN", f.PGDSN),
		Port:                env("DOCS_SEARCH_PORT", f.Port),
		Deployments:         map[string]string{},
	}
	if c.AICoreResourceGroup == "" {
		c.AICoreResourceGroup = "default"
	}
	if c.Port == "" {
		c.Port = "8081"
	}
	for _, m := range f.Models {
		c.Deployments[m.Name] = m.DeploymentID
	}
	for k, v := range map[string]string{
		"AICORE_AUTH_URL": c.AICoreAuthURL, "AICORE_BASE_URL": c.AICoreBaseURL,
		"AICORE_CLIENT_ID": c.AICoreClientID, "AICORE_CLIENT_SECRET": c.AICoreClientSecret,
		"MAIN_EMBEDDING_MODEL_NAME": c.EmbeddingModel, "MAIN_MODEL_MINI_NAME": c.MiniModel,
		"DOCS_SEARCH_PG_DSN": c.PGDSN,
	} {
		if v == "" {
			return Config{}, fmt.Errorf("missing config key %s", k)
		}
	}
	for _, m := range []string{c.EmbeddingModel, c.MiniModel} {
		if c.Deployments[m] == "" {
			return Config{}, fmt.Errorf("no deployment_id for model %q in models", m)
		}
	}
	return c, nil
}
