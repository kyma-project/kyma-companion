// Package telemetry sets up OpenTelemetry tracing. The exporter is off unless
// OTEL_EXPORTER_OTLP_ENDPOINT is set; all other OTEL_* variables are read by the SDK itself.
package telemetry

import (
	"context"
	"log/slog"
	"os"
	"strings"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
)

// Version is set via -ldflags "-X github.com/kyma-project/kyma-docs-search/internal/telemetry.Version=...".
var Version = "dev"

var traceContent = strings.EqualFold(os.Getenv("DOCS_SEARCH_TRACE_CONTENT"), "true")

// ContentEnabled reports whether query text and prompts may be put into span attributes.
// For local demos only (DOCS_SEARCH_TRACE_CONTENT=true); keep it off in production.
func ContentEnabled() bool { return traceContent }

// Tracer returns a tracer with the given instrumentation name.
func Tracer(name string) trace.Tracer { return otel.Tracer(name) }

// Fail records err on the span and marks it as failed.
func Fail(span trace.Span, err error) {
	span.RecordError(err)
	span.SetStatus(codes.Error, err.Error())
}

// Content returns a string attribute only when content tracing is enabled.
func Content(key, value string) []attribute.KeyValue {
	if !traceContent {
		return nil
	}
	return []attribute.KeyValue{attribute.String(key, value)}
}

// ContentStrings is Content for string slices.
func ContentStrings(key string, value []string) []attribute.KeyValue {
	if !traceContent {
		return nil
	}
	return []attribute.KeyValue{attribute.StringSlice(key, value)}
}

// Setup configures the global tracer provider and propagator. The returned function flushes and shuts down.
func Setup(ctx context.Context) (func(context.Context) error, error) {
	otel.SetTextMapPropagator(propagation.TraceContext{})
	if os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT") == "" && os.Getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") == "" {
		// A provider without span processor: spans get valid ids (for x-trace-id and propagation) but are never exported.
		otel.SetTracerProvider(sdktrace.NewTracerProvider())
		slog.Info("tracing disabled (OTEL_EXPORTER_OTLP_ENDPOINT unset)")
		return func(context.Context) error { return nil }, nil
	}
	exp, err := otlptracehttp.New(ctx)
	if err != nil {
		return nil, err
	}
	res := resource.NewWithAttributes(semconv.SchemaURL,
		semconv.ServiceName("kyma-docs-search"), semconv.ServiceVersion(Version))
	tp := sdktrace.NewTracerProvider(sdktrace.WithBatcher(exp), sdktrace.WithResource(res))
	otel.SetTracerProvider(tp)
	if traceContent {
		slog.Warn("DOCS_SEARCH_TRACE_CONTENT=true: queries and prompts are exported in spans (demo use only)")
	}
	slog.Info("tracing enabled", "service.version", Version)
	return tp.Shutdown, nil
}
