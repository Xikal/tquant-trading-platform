package main

import (
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

type config struct {
	addr              string
	pythonAPIBase     string
	internalToken     string
	timeout           time.Duration
	workspaceCacheTTL time.Duration
}

func main() {
	cfg := loadConfig()
	client := &http.Client{Timeout: cfg.timeout}
	cache := newWorkspaceCache(cfg.workspaceCacheTTL)
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", healthHandler)
	mux.HandleFunc("/readyz", healthHandler)
	mux.HandleFunc("/metrics", metricsHandler)
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
	return config{
		addr:              ":" + env("PORT", "8091"),
		pythonAPIBase:     strings.TrimRight(env("TQUANT_PYTHON_API_BASE", "http://127.0.0.1:8000"), "/"),
		internalToken:     os.Getenv("TQUANT_INTERNAL_SERVICE_TOKEN"),
		timeout:           durationSeconds("TQUANT_SERVICE_CALL_TIMEOUT_SECONDS", 5),
		workspaceCacheTTL: durationSeconds("BFF_WORKSPACE_CACHE_TTL_SECONDS", 5),
	}
}

func healthHandler(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, `{"ok":true}`)
}

func metricsHandler(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	_, _ = w.Write([]byte("tquant_bff_gateway_up 1\n"))
}

func manifestHandler(cache *workspaceCache) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if cached, ok := cache.get(workspaceCacheKey(r)); ok {
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
		if cached, ok := cache.get(workspaceCacheKey(r)); ok {
			if cached.contentType != "" {
				w.Header().Set("Content-Type", cached.contentType)
			}
			w.Header().Set("X-BFF-Cache", "HIT")
			w.WriteHeader(cached.status)
			_, _ = w.Write(cached.body)
			return
		}
		if result := aggregateWorkspace(cfg, client, r); result.ok {
			cache.set(workspaceCacheKey(r), result.status, result.body, result.contentType)
			writeAggregate(w, result)
			return
		}
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
		r.Header.Set("X-Request-ID", requestID)
		w.Header().Set("X-Request-ID", requestID)
		next.ServeHTTP(w, r)
	})
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
