package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

var errMissingProductionInternalToken = errors.New("TQUANT_INTERNAL_SERVICE_TOKEN is required when APP_ENVIRONMENT=production")

var marketReadHits atomic.Int64
var marketReadFallbacks atomic.Int64
var marketReadPartials atomic.Int64

func main() {
	token := strings.TrimSpace(os.Getenv("TQUANT_INTERNAL_SERVICE_TOKEN"))
	if err := validateInternalToken(token); err != nil {
		panic(err)
	}
	cache := newMarketReadCache(
		env("REDIS_URL", "redis://redis:6379/0"),
		env("MYSQL_DSN", env("DATABASE_URL", "")),
	)
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", health)
	mux.HandleFunc("/readyz", health)
	mux.HandleFunc("/metrics", metrics)
	mux.Handle("/api/market-read/v1/quote-batch", internalOnly(token, quoteBatchHandler(cache)))
	mux.Handle("/api/market-read/v1/intraday-latest-batch", internalOnly(token, intradayLatestBatchHandler(cache)))
	mux.Handle("/api/market-read/v1/sector-relative-strength", internalOnly(token, sectorStrengthHandler(cache)))
	mux.Handle("/api/market-read/v1/intraday-key-levels", internalOnly(token, intradayKeyLevelsHandler(cache)))
	server := withTimeout(mux)
	_ = server.ListenAndServe()
}

func health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":                   true,
		"service":              "market-read-service",
		"production_readiness": "mainline_ready",
		"source":               "redis_local_quote_cache",
	})
}

func metrics(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	lines := []string{
		"tquant_market_read_service_up 1",
		"tquant_market_read_hits_total " + strconv.FormatInt(marketReadHits.Load(), 10),
		"tquant_market_read_fallbacks_total " + strconv.FormatInt(marketReadFallbacks.Load(), 10),
		"tquant_market_read_partials_total " + strconv.FormatInt(marketReadPartials.Load(), 10),
	}
	_, _ = w.Write([]byte(strings.Join(lines, "\n") + "\n"))
}

func notEnabled(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":                   true,
		"production_readiness": "mainline_ready",
		"detail":               "Go market read service is production-ready for internal read-through local quote cache paths",
	})
}

type quoteCache interface {
	Get(ctx context.Context, key string) ([]byte, error)
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

func withTimeout(next http.Handler) *http.Server {
	return &http.Server{
		Addr:              ":" + env("PORT", "8092"),
		Handler:           next,
		ReadHeaderTimeout: 5 * time.Second,
	}
}

func writeJSON(w http.ResponseWriter, status int, payload map[string]any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	writeJSONPayload(w, payload)
}

func env(key string, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
