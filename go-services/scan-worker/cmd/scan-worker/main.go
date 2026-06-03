package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
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
	pythonAPIBase string
	internalToken string
	timeout       time.Duration
}

var scanRuns atomic.Int64
var scanAccepted atomic.Int64
var scanFailures atomic.Int64
var scanFallbacks atomic.Int64
var scanWrites atomic.Int64

const (
	scanWorkerRole        = "go_orchestrated_reference"
	scanStrategyEngine    = "python_reference"
	scanProductionStatus  = "python_reference_orchestrator"
	scanRankingStatus     = "python_reference_order"
	scanRankingStatusText = "Go scan-worker invokes the Python reference strategy engine and only publishes when that reference write succeeds."
)

func main() {
	cfg := loadConfig()
	client := &http.Client{Timeout: cfg.timeout}
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", health)
	mux.HandleFunc("/readyz", health)
	mux.HandleFunc("/metrics", metrics)
	mux.Handle("/api/scan-worker/v1/status", internalOnly(cfg.internalToken, http.HandlerFunc(statusHandler)))
	mux.Handle("/api/scan-worker/v1/run", internalOnly(cfg.internalToken, runHandler(cfg, client)))
	server := &http.Server{
		Addr:              ":" + env("PORT", "8093"),
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	_ = server.ListenAndServe()
}

func loadConfig() config {
	token := strings.TrimSpace(os.Getenv("TQUANT_INTERNAL_SERVICE_TOKEN"))
	if err := validateInternalToken(token); err != nil {
		panic(err)
	}
	return config{
		pythonAPIBase: strings.TrimRight(env("TQUANT_PYTHON_API_BASE", "http://127.0.0.1:8000"), "/"),
		internalToken: token,
		timeout:       durationSeconds("TQUANT_SERVICE_CALL_TIMEOUT_SECONDS", 30),
	}
}

func health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":                   true,
		"service":              "scan-worker",
		"production_readiness": scanProductionStatus,
		"scan_worker_role":     scanWorkerRole,
		"strategy_engine":      scanStrategyEngine,
	})
}

func metrics(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	lines := []string{
		"tquant_scan_worker_up 1",
		fmt.Sprintf("tquant_scan_worker_runs_total %d", scanRuns.Load()),
		fmt.Sprintf("tquant_scan_worker_accepted_total %d", scanAccepted.Load()),
		fmt.Sprintf("tquant_scan_worker_failures_total %d", scanFailures.Load()),
		fmt.Sprintf("tquant_scan_worker_fallbacks_total %d", scanFallbacks.Load()),
		fmt.Sprintf("tquant_scan_worker_snapshot_writes_total %d", scanWrites.Load()),
	}
	_, _ = w.Write([]byte(strings.Join(lines, "\n") + "\n"))
}

func statusHandler(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":                       true,
		"production_scan_enabled":  true,
		"production_write_enabled": true,
		"production_readiness":     scanProductionStatus,
		"scan_worker_role":         scanWorkerRole,
		"strategy_engine":          scanStrategyEngine,
		"fallback_available":       true,
		"ranking_consistency": map[string]any{
			"checked": true,
			"status":  scanRankingStatus,
			"detail":  scanRankingStatusText,
		},
		"scan_runs_total":       scanRuns.Load(),
		"scan_accepted_total":   scanAccepted.Load(),
		"scan_failures_total":   scanFailures.Load(),
		"scan_fallbacks_total":  scanFallbacks.Load(),
		"snapshot_writes_total": scanWrites.Load(),
	})
}

func runHandler(cfg config, client *http.Client) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		scanRuns.Add(1)
		result, status, err := callPythonReference(cfg, client, r)
		if err != nil {
			scanFailures.Add(1)
			scanFallbacks.Add(1)
			writeJSON(w, http.StatusBadGateway, map[string]any{
				"ok":                       false,
				"status":                   "fallback_available",
				"production_scan_enabled":  true,
				"production_write_enabled": false,
				"production_readiness":     scanProductionStatus,
				"scan_worker_role":         scanWorkerRole,
				"strategy_engine":          scanStrategyEngine,
				"fallback_available":       true,
				"fallback_reason":          err.Error(),
				"detail":                   "scan-worker could not complete the production scan; Python fallback should be used by caller.",
			})
			return
		}
		if status == http.StatusAccepted {
			scanAccepted.Add(1)
			result["accepted"] = true
			result["status"] = "accepted"
		} else if ok, _ := result["ok"].(bool); ok {
			scanWrites.Add(1)
			if strings.TrimSpace(fmt.Sprint(result["status"])) == "" {
				result["status"] = "queued"
			}
		} else {
			scanFailures.Add(1)
			if strings.TrimSpace(fmt.Sprint(result["status"])) == "" {
				result["status"] = "failed"
			}
		}
		result["production_scan_enabled"] = true
		result["production_write_enabled"] = true
		result["production_readiness"] = scanProductionStatus
		result["fallback_available"] = true
		result["scan_worker_source"] = scanWorkerRole
		result["scan_worker_role"] = scanWorkerRole
		result["strategy_engine"] = scanStrategyEngine
		writeJSON(w, status, result)
	})
}

func callPythonReference(cfg config, client *http.Client, incoming *http.Request) (map[string]any, int, error) {
	target, err := url.Parse(cfg.pythonAPIBase + "/api/internal/scan-worker/v1/run")
	if err != nil {
		return nil, 0, err
	}
	q := target.Query()
	for _, key := range []string{"strategies", "strategy", "scan_limit", "limit", "reason"} {
		if value := strings.TrimSpace(incoming.URL.Query().Get(key)); value != "" {
			if key == "strategy" {
				q.Set("strategies", value)
			} else {
				q.Set(key, value)
			}
		}
	}
	target.RawQuery = q.Encode()
	req, err := http.NewRequestWithContext(incoming.Context(), http.MethodGet, target.String(), nil)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("X-TQuant-Bff-Hop", "1")
	if cfg.internalToken != "" {
		req.Header.Set("X-Internal-Service-Token", cfg.internalToken)
	}
	copyHeader(req.Header, incoming.Header, "X-Request-ID")
	resp, err := client.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, 0, err
	}
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return nil, resp.StatusCode, fmt.Errorf("python reference returned status %d", resp.StatusCode)
	}
	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, resp.StatusCode, err
	}
	return payload, resp.StatusCode, nil
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

func copyHeader(dst http.Header, src http.Header, key string) {
	if value := src.Get(key); value != "" {
		dst.Set(key, value)
	}
}
