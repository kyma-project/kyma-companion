// Package prompts embeds the LLM prompt templates.
package prompts

import _ "embed"

//go:embed query_generator_system.txt
var QueryGeneratorSystem string

//go:embed query_generator_followup.txt
var QueryGeneratorFollowup string

//go:embed reranker.txt
var Reranker string
