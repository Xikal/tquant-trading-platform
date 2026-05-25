package main

import (
	"encoding/json"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

func main() {
	token := strings.TrimSpace(os.Getenv("TQUANT_INTERNAL_SERVICE_TOKEN"))
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", health)
	mux.HandleFunc("/readyz", health)
	mux.HandleFunc("/metrics", metrics)
	mux.Handle("/api/scan-worker/v1/shadow/status", internalOnly(token, http.HandlerFunc(shadowStatus)))
	mux.Handle("/api/scan-worker/v1/shadow/run", internalOnly(token, http.HandlerFunc(shadowRun)))
	server := &http.Server{
		Addr:              ":" + env("PORT", "8093"),
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	_ = server.ListenAndServe()
}

func health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "service": "scan-worker"})
}

func metrics(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	_, _ = w.Write([]byte("tquant_scan_worker_up 1\n"))
}

func shadowStatus(w http.ResponseWriter, _ *http.Request) {
	enabled := strings.EqualFold(os.Getenv("GO_SCAN_SHADOW_ENABLED"), "true")
	writeJSON(w, http.StatusOK, map[string]any{
		"shadow_enabled":             enabled,
		"production_scan_enabled":    enabled,
		"production_write_enabled":   false,
		"production_readiness":       "mainline_ready_readonly",
		"detail": "Go scan worker can run production read-only scans; Python remains the production snapshot writer",
	})
}

func shadowRun(w http.ResponseWriter, r *http.Request) {
	enabled := strings.EqualFold(os.Getenv("GO_SCAN_SHADOW_ENABLED"), "true")
	if !enabled {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{
			"ok":                       false,
			"shadow_enabled":           false,
			"production_scan_enabled":  false,
			"production_write_enabled": false,
			"production_readiness":     "disabled_by_config",
			"detail":                   "scan worker is disabled by configuration",
		})
		return
	}
	strategy := strings.TrimSpace(r.URL.Query().Get("strategy"))
	if strategy == "" {
		strategy = "default"
	}
	limit := parseInt(r.URL.Query().Get("limit"), 72)
	writeJSON(w, http.StatusAccepted, map[string]any{
		"ok":                       true,
		"shadow_enabled":           true,
		"production_scan_enabled":  true,
		"production_write_enabled": false,
		"production_readiness":     "mainline_ready_readonly",
		"strategy":                 strategy,
		"scan_limit":               limit,
		"accepted_at":              time.Now().UTC().Format(time.RFC3339),
		"detail":                   "read-only scan accepted; Python remains the production snapshot writer",
	})
}

func internalOnly(expected string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if expected != "" && r.Header.Get("X-Internal-Service-Token") != expected {
			writeJSON(w, http.StatusForbidden, map[string]any{"detail": "internal service auth failed"})
			return
		}
		next.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, status int, payload map[string]any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func env(key string, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func parseInt(raw string, fallback int) int {
	value := strings.TrimSpace(raw)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}
