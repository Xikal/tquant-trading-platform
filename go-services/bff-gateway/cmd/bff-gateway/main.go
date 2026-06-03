package main

import (
	crand "crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

var errMissingProductionInternalToken = errors.New("TQUANT_INTERNAL_SERVICE_TOKEN is required when APP_ENVIRONMENT=production")

type config struct {
	addr              string
	pythonAPIBase     string
	internalToken     string
	timeout           time.Duration
	sourceTimeout     time.Duration
	workspaceCacheTTL time.Duration
}

var bffAggregateHits atomic.Int64
var bffProxyFallbacks atomic.Int64
var bffCacheHits atomic.Int64
var bffCacheLookups atomic.Int64
var bffPartialSourceFailures atomic.Int64
var bffPartialTimeoutFailures atomic.Int64
var bffPartialStatusFailures atomic.Int64
var bffPartialDecodeFailures atomic.Int64
var bffPartialOtherFailures atomic.Int64
var bffWorkspaceAggregateMonitorHits atomic.Int64
var bffWorkspaceAggregatePaperHits atomic.Int64
var bffWorkspaceAggregateStrategyHits atomic.Int64
var bffWorkspaceAggregateStrategyTrackingHits atomic.Int64
var bffWorkspaceAggregateSettingsHits atomic.Int64
var bffWorkspaceAggregateFactorHits atomic.Int64
var bffWorkspaceProxyMonitorFallbacks atomic.Int64
var bffWorkspaceProxyPaperFallbacks atomic.Int64
var bffWorkspaceProxyStrategyFallbacks atomic.Int64
var bffWorkspaceProxyStrategyTrackingFallbacks atomic.Int64
var bffWorkspaceProxySettingsFallbacks atomic.Int64
var bffWorkspaceProxyFactorFallbacks atomic.Int64

func main() {
	cfg := loadConfig()
	client := &http.Client{Timeout: cfg.timeout}
	cache := newWorkspaceCache(cfg.workspaceCacheTTL)
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", healthHandler)
	mux.HandleFunc("/readyz", healthHandler)
	mux.HandleFunc("/metrics", metricsHandler(cache))
	mux.HandleFunc("/api/bff/v1/manifest", manifestHandler(cache))
	mux.HandleFunc("/bff/v1/manifest", manifestHandler(cache))
	mux.HandleFunc("/api/bff/v1/workspace/", proxyWorkspaceHandler(cfg, client, cache))
	mux.HandleFunc("/bff/v1/workspace/", proxyWorkspaceHandler(cfg, client, cache))

	server := &http.Server{
		Addr:              cfg.addr,
		Handler:           requestIDMiddleware(mux),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Printf("tquant bff-gateway listening addr=%s python_api_base=%s", cfg.addr, cfg.pythonAPIBase)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("server failed: %v", err)
	}
}

func loadConfig() config {
	internalToken := strings.TrimSpace(os.Getenv("TQUANT_INTERNAL_SERVICE_TOKEN"))
	if err := validateInternalToken(internalToken); err != nil {
		log.Fatal(err)
	}
	return config{
		addr:              ":" + env("PORT", "8091"),
		pythonAPIBase:     strings.TrimRight(env("TQUANT_PYTHON_API_BASE", "http://127.0.0.1:8000"), "/"),
		internalToken:     internalToken,
		timeout:           durationSeconds("TQUANT_SERVICE_CALL_TIMEOUT_SECONDS", 5),
		sourceTimeout:     durationSeconds("BFF_SOURCE_TIMEOUT_SECONDS", 1),
		workspaceCacheTTL: durationSeconds("BFF_WORKSPACE_CACHE_TTL_SECONDS", 5),
	}
}

func productionProfile() bool {
	value := strings.ToLower(strings.TrimSpace(env("APP_ENVIRONMENT", env("APP_ENV", ""))))
	return value == "production" || value == "prod" || value == "cloud"
}

func validateInternalToken(token string) error {
	if productionProfile() && strings.TrimSpace(token) == "" {
		return errMissingProductionInternalToken
	}
	return nil
}

func healthHandler(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, `{"ok":true}`)
}

func metricsHandler(cache *workspaceCache) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		lookups := bffCacheLookups.Load()
		cacheHits := bffCacheHits.Load()
		hitRate := 0.0
		if lookups > 0 {
			hitRate = float64(cacheHits) / float64(lookups)
		}
		lines := []string{
			"tquant_bff_gateway_up 1",
			"tquant_bff_gateway_aggregate_hits_total " + strconv.FormatInt(bffAggregateHits.Load(), 10),
			"tquant_bff_gateway_proxy_fallbacks_total " + strconv.FormatInt(bffProxyFallbacks.Load(), 10),
			"tquant_bff_gateway_cache_lookups_total " + strconv.FormatInt(lookups, 10),
			"tquant_bff_gateway_cache_hits_total " + strconv.FormatInt(bffCacheHits.Load(), 10),
			"tquant_bff_gateway_cache_hit_rate " + strconv.FormatFloat(hitRate, 'f', 6, 64),
			"tquant_bff_gateway_cache_items " + strconv.Itoa(cache.size()),
			"tquant_bff_gateway_cache_ttl_seconds " + strconv.FormatFloat(cache.ttlSeconds(), 'f', 3, 64),
			"tquant_bff_gateway_partial_source_failures_total " + strconv.FormatInt(bffPartialSourceFailures.Load(), 10),
			"tquant_bff_gateway_partial_source_failures_total{reason=\"timeout\"} " + strconv.FormatInt(bffPartialTimeoutFailures.Load(), 10),
			"tquant_bff_gateway_partial_source_failures_total{reason=\"status\"} " + strconv.FormatInt(bffPartialStatusFailures.Load(), 10),
			"tquant_bff_gateway_partial_source_failures_total{reason=\"decode\"} " + strconv.FormatInt(bffPartialDecodeFailures.Load(), 10),
			"tquant_bff_gateway_partial_source_failures_total{reason=\"other\"} " + strconv.FormatInt(bffPartialOtherFailures.Load(), 10),
			"tquant_bff_gateway_workspace_aggregate_hits_total{workspace=\"monitor\"} " + strconv.FormatInt(bffWorkspaceAggregateMonitorHits.Load(), 10),
			"tquant_bff_gateway_workspace_aggregate_hits_total{workspace=\"paper\"} " + strconv.FormatInt(bffWorkspaceAggregatePaperHits.Load(), 10),
			"tquant_bff_gateway_workspace_aggregate_hits_total{workspace=\"strategy\"} " + strconv.FormatInt(bffWorkspaceAggregateStrategyHits.Load(), 10),
			"tquant_bff_gateway_workspace_aggregate_hits_total{workspace=\"strategy-tracking\"} " + strconv.FormatInt(bffWorkspaceAggregateStrategyTrackingHits.Load(), 10),
			"tquant_bff_gateway_workspace_aggregate_hits_total{workspace=\"settings\"} " + strconv.FormatInt(bffWorkspaceAggregateSettingsHits.Load(), 10),
			"tquant_bff_gateway_workspace_aggregate_hits_total{workspace=\"factor\"} " + strconv.FormatInt(bffWorkspaceAggregateFactorHits.Load(), 10),
			"tquant_bff_gateway_workspace_proxy_fallbacks_total{workspace=\"monitor\"} " + strconv.FormatInt(bffWorkspaceProxyMonitorFallbacks.Load(), 10),
			"tquant_bff_gateway_workspace_proxy_fallbacks_total{workspace=\"paper\"} " + strconv.FormatInt(bffWorkspaceProxyPaperFallbacks.Load(), 10),
			"tquant_bff_gateway_workspace_proxy_fallbacks_total{workspace=\"strategy\"} " + strconv.FormatInt(bffWorkspaceProxyStrategyFallbacks.Load(), 10),
			"tquant_bff_gateway_workspace_proxy_fallbacks_total{workspace=\"strategy-tracking\"} " + strconv.FormatInt(bffWorkspaceProxyStrategyTrackingFallbacks.Load(), 10),
			"tquant_bff_gateway_workspace_proxy_fallbacks_total{workspace=\"settings\"} " + strconv.FormatInt(bffWorkspaceProxySettingsFallbacks.Load(), 10),
			"tquant_bff_gateway_workspace_proxy_fallbacks_total{workspace=\"factor\"} " + strconv.FormatInt(bffWorkspaceProxyFactorFallbacks.Load(), 10),
		}
		lines = append(lines, partialSourceReasonMetricsLines()...)
		_, _ = w.Write([]byte(strings.Join(lines, "\n") + "\n"))
	}
}

func manifestHandler(cache *workspaceCache) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		bffCacheLookups.Add(1)
		if cached, ok := cache.get(workspaceCacheKey(r)); ok {
			bffCacheHits.Add(1)
			if cached.contentType != "" {
				w.Header().Set("Content-Type", cached.contentType)
			}
			w.Header().Set("X-BFF-Cache", "HIT")
			w.WriteHeader(cached.status)
			_, _ = w.Write(cached.body)
			return
		}
		result := aggregateManifest()
		cache.set(workspaceCacheKey(r), result.status, result.body, result.contentType)
		writeAggregate(w, result)
	}
}

func proxyWorkspaceHandler(cfg config, client *http.Client, cache *workspaceCache) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if cfg.internalToken != "" && r.Header.Get("X-Internal-Service-Token") != cfg.internalToken {
			writeJSON(w, http.StatusForbidden, `{"detail":"internal service auth failed"}`)
			return
		}
		bffCacheLookups.Add(1)
		if cached, ok := cache.get(workspaceCacheKey(r)); ok {
			bffCacheHits.Add(1)
			if cached.contentType != "" {
				w.Header().Set("Content-Type", cached.contentType)
			}
			w.Header().Set("X-BFF-Cache", "HIT")
			w.WriteHeader(cached.status)
			_, _ = w.Write(cached.body)
			return
		}
		workspace := workspaceName(r.URL.Path)
		if result := aggregateWorkspace(cfg, client, r); result.ok {
			bffAggregateHits.Add(1)
			incrementWorkspaceAggregate(workspace)
			cache.set(workspaceCacheKey(r), result.status, result.body, result.contentType)
			writeAggregate(w, result)
			return
		}
		bffProxyFallbacks.Add(1)
		incrementWorkspaceProxyFallback(workspace)
		target, err := workspaceTargetURL(cfg.pythonAPIBase, r)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, `{"detail":"invalid workspace request"}`)
			return
		}
		req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, target, nil)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, `{"detail":"proxy request build failed"}`)
			return
		}
		copyHeader(req.Header, r.Header, "Authorization")
		copyHeader(req.Header, r.Header, "X-Admin-Token")
		copyHeader(req.Header, r.Header, "X-Request-ID")
		copyHeader(req.Header, r.Header, "traceparent")
		req.Header.Set("X-TQuant-Bff-Hop", "1")
		if cfg.internalToken != "" {
			req.Header.Set("X-Internal-Service-Token", cfg.internalToken)
		}
		resp, err := client.Do(req)
		if err != nil {
			writeJSON(w, http.StatusBadGateway, `{"detail":"python bff unavailable"}`)
			return
		}
		defer resp.Body.Close()
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			writeJSON(w, http.StatusBadGateway, `{"detail":"python bff response read failed"}`)
			return
		}
		copyResponseHeaders(w.Header(), resp.Header)
		cache.set(workspaceCacheKey(r), resp.StatusCode, body, resp.Header.Get("Content-Type"))
		w.WriteHeader(resp.StatusCode)
		_, _ = w.Write(body)
	}
}

func incrementWorkspaceAggregate(workspace string) {
	switch workspace {
	case "monitor":
		bffWorkspaceAggregateMonitorHits.Add(1)
	case "paper":
		bffWorkspaceAggregatePaperHits.Add(1)
	case "strategy":
		bffWorkspaceAggregateStrategyHits.Add(1)
	case "strategy-tracking":
		bffWorkspaceAggregateStrategyTrackingHits.Add(1)
	case "settings":
		bffWorkspaceAggregateSettingsHits.Add(1)
	case "factor":
		bffWorkspaceAggregateFactorHits.Add(1)
	}
}

func incrementWorkspaceProxyFallback(workspace string) {
	switch workspace {
	case "monitor":
		bffWorkspaceProxyMonitorFallbacks.Add(1)
	case "paper":
		bffWorkspaceProxyPaperFallbacks.Add(1)
	case "strategy":
		bffWorkspaceProxyStrategyFallbacks.Add(1)
	case "strategy-tracking":
		bffWorkspaceProxyStrategyTrackingFallbacks.Add(1)
	case "settings":
		bffWorkspaceProxySettingsFallbacks.Add(1)
	case "factor":
		bffWorkspaceProxyFactorFallbacks.Add(1)
	}
}

func writeAggregate(w http.ResponseWriter, result aggregateResult) {
	if result.contentType != "" {
		w.Header().Set("Content-Type", result.contentType)
	}
	w.Header().Set("X-BFF-Aggregated", "1")
	w.WriteHeader(result.status)
	_, _ = w.Write(result.body)
}

func workspaceTargetURL(base string, r *http.Request) (string, error) {
	path := r.URL.Path
	if strings.HasPrefix(path, "/bff/") {
		path = "/api" + path
	}
	parsed, err := url.Parse(base + path)
	if err != nil {
		return "", err
	}
	parsed.RawQuery = r.URL.RawQuery
	return parsed.String(), nil
}

func requestIDMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestID := r.Header.Get("X-Request-ID")
		if requestID == "" {
			requestID = "go-" + time.Now().UTC().Format("20060102150405.000000000")
		}
		traceparent := r.Header.Get("traceparent")
		if traceparent == "" {
			traceparent = newTraceparent()
			r.Header.Set("traceparent", traceparent)
		}
		r.Header.Set("X-Request-ID", requestID)
		w.Header().Set("X-Request-ID", requestID)
		w.Header().Set("traceparent", traceparent)
		next.ServeHTTP(w, r)
	})
}

func newTraceparent() string {
	var buf [24]byte
	if _, err := crand.Read(buf[:]); err == nil {
		return "00-" + hex.EncodeToString(buf[:16]) + "-" + hex.EncodeToString(buf[16:]) + "-01"
	}
	now := uint64(time.Now().UTC().UnixNano())
	traceID := fmt.Sprintf("%016x%016x", now, now^0x9e3779b97f4a7c15)
	spanID := fmt.Sprintf("%016x", now^0x517cc1b727220a95)
	return "00-" + traceID + "-" + spanID + "-01"
}

func copyHeader(dst http.Header, src http.Header, key string) {
	if value := src.Get(key); value != "" {
		dst.Set(key, value)
	}
}

func copyResponseHeaders(dst http.Header, src http.Header) {
	keep := map[string]bool{
		"content-type":     true,
		"x-request-id":     true,
		"traceparent":      true,
		"cache-control":    true,
		"etag":             true,
		"last-modified":    true,
		"content-language": true,
	}
	for key, values := range src {
		if !keep[strings.ToLower(key)] {
			continue
		}
		for _, value := range values {
			dst.Add(key, value)
		}
	}
}

func writeJSON(w http.ResponseWriter, status int, payload string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(payload))
}

func env(key string, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func durationSeconds(key string, fallback int) time.Duration {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return time.Duration(fallback) * time.Second
	}
	if duration, err := time.ParseDuration(value); err == nil {
		return duration
	}
	if seconds, err := strconv.ParseFloat(value, 64); err == nil && seconds > 0 {
		return time.Duration(seconds * float64(time.Second))
	}
	return time.Duration(fallback) * time.Second
}
