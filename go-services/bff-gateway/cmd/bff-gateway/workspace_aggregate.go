package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

const schemaVersion = "v13"

type aggregateResult struct {
	status      int
	body        []byte
	contentType string
	ok          bool
}

type partialError struct {
	Source string `json:"source"`
	Detail string `json:"detail"`
}

type rawSource struct {
	name  string
	path  string
	query url.Values
}

func aggregateWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	workspace := workspaceName(r.URL.Path)
	switch workspace {
	case "monitor":
		return aggregateMonitorWorkspace(cfg, client, r)
	case "paper":
		return aggregatePaperWorkspace(cfg, client, r)
	default:
		return aggregateResult{}
	}
}

func aggregateManifest() aggregateResult {
	payload := map[string]any{
		"api_version":    "v1",
		"bff_version":    "v1",
		"schema_version": schemaVersion,
		"gateway_prefix": "/api",
		"modules": []string{
			"auth",
			"market",
			"strategy",
			"trade",
			"factor",
			"monitor",
			"settings",
		},
		"workspaces": map[string]any{
			"monitor": map[string]any{"path": "/api/bff/v1/workspace/monitor", "schema_version": schemaVersion, "model": "MonitorWorkspaceBffResponse"},
			"paper":   map[string]any{"path": "/api/bff/v1/workspace/paper", "schema_version": schemaVersion, "model": "PaperWorkspaceBffResponse"},
			"strategy": map[string]any{
				"path":           "/api/bff/v1/workspace/strategy",
				"schema_version": schemaVersion,
				"model":          "StrategyWorkspaceBffResponse",
			},
			"settings": map[string]any{"path": "/api/bff/v1/workspace/settings", "schema_version": schemaVersion, "model": "SettingsWorkspaceBffResponse"},
		},
	}
	return jsonPayload(http.StatusOK, payload)
}

func aggregateMonitorWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	q := r.URL.Query()
	sources := []rawSource{
		{name: "monitor_snapshot", path: "/api/monitor/snapshot", query: values("priority_limit", queryDefault(q, "priority_limit", "12"))},
		{name: "market_breadth", path: "/api/market/breadth", query: values("realtime", "true")},
		{name: "sector_relative_strength", path: "/api/market/sector-relative-strength", query: values(
			"limit", queryDefault(q, "sector_limit", "8"),
			"per_sector_limit", queryDefault(q, "per_sector_limit", "8"),
		)},
		{name: "paired_hedge", path: "/api/market/paired-hedge-research", query: values("limit", queryDefault(q, "hedge_limit", "4"))},
	}
	results, errors := fetchSources(cfg, client, r, sources)
	payload := map[string]any{
		"api_version":              "v1",
		"schema_version":           schemaVersion,
		"generated_at":             beijingNowString(),
		"monitor_snapshot":         nullableJSON(results["monitor_snapshot"]),
		"market_breadth":           nullableJSON(results["market_breadth"]),
		"sector_relative_strength": nullableJSON(results["sector_relative_strength"]),
		"paired_hedge":             nullableJSON(results["paired_hedge"]),
		"partial_errors":           errors,
	}
	return jsonPayload(http.StatusOK, payload)
}

func aggregatePaperWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	q := r.URL.Query()
	sources := []rawSource{
		{name: "account", path: "/api/paper/account"},
		{name: "positions", path: "/api/paper/positions"},
		{name: "orders", path: "/api/paper/orders", query: values("limit", queryDefault(q, "order_limit", "80"))},
		{name: "trades", path: "/api/paper/trades", query: values("limit", queryDefault(q, "trade_limit", "300"))},
		{name: "stock_pnl", path: "/api/paper/performance/stock-pnl"},
		{name: "performance", path: "/api/paper/performance"},
		{name: "sector_etf_t0_performance", path: "/api/paper/performance/sector-etf-t0"},
		{name: "strategy_performance", path: "/api/paper/performance/by-strategy"},
		{name: "market_performance", path: "/api/paper/performance/by-market-state"},
		{name: "tag_performance", path: "/api/paper/performance/by-tag"},
		{name: "risk_events", path: "/api/paper/risk/events", query: values("limit", "50")},
		{name: "auto_trading_status", path: "/api/paper/auto-trading/status"},
		{name: "auto_trading_runs", path: "/api/paper/auto-trading/runs", query: values("limit", queryDefault(q, "run_limit", "20"))},
	}
	results, errors := fetchSources(cfg, client, r, sources)
	payload := map[string]any{
		"api_version":               "v1",
		"schema_version":            schemaVersion,
		"generated_at":              beijingNowString(),
		"account":                   nullableJSON(results["account"]),
		"positions":                 jsonArrayField(results["positions"], "positions"),
		"orders":                    jsonArray(results["orders"]),
		"trades":                    jsonArrayField(results["trades"], "trades"),
		"stock_pnl":                 nullableJSON(results["stock_pnl"]),
		"performance":               nullableJSON(results["performance"]),
		"sector_etf_t0_performance": nullableJSON(results["sector_etf_t0_performance"]),
		"strategy_performance":      jsonArray(results["strategy_performance"]),
		"market_performance":        jsonArray(results["market_performance"]),
		"tag_performance":           jsonArray(results["tag_performance"]),
		"risk_events":               jsonArray(results["risk_events"]),
		"auto_trading_status":       jsonObject(results["auto_trading_status"]),
		"auto_trading_runs":         jsonArray(results["auto_trading_runs"]),
		"partial_errors":            errors,
	}
	return jsonPayload(http.StatusOK, payload)
}

func fetchSources(cfg config, client *http.Client, r *http.Request, sources []rawSource) (map[string]json.RawMessage, []partialError) {
	results := make(map[string]json.RawMessage, len(sources))
	errors := make([]partialError, 0)
	var mu sync.Mutex
	var wg sync.WaitGroup
	for _, source := range sources {
		wg.Add(1)
		go func(source rawSource) {
			defer wg.Done()
			body, err := fetchRawSource(cfg, client, r, source)
			mu.Lock()
			defer mu.Unlock()
			if err != nil {
				errors = append(errors, partialError{Source: source.name, Detail: "数据暂时不可用"})
				return
			}
			results[source.name] = body
		}(source)
	}
	wg.Wait()
	return results, errors
}

func fetchRawSource(cfg config, client *http.Client, incoming *http.Request, source rawSource) (json.RawMessage, error) {
	target, err := url.Parse(cfg.pythonAPIBase + source.path)
	if err != nil {
		return nil, err
	}
	target.RawQuery = source.query.Encode()
	req, err := http.NewRequestWithContext(incoming.Context(), http.MethodGet, target.String(), nil)
	if err != nil {
		return nil, err
	}
	copyHeader(req.Header, incoming.Header, "Authorization")
	copyHeader(req.Header, incoming.Header, "X-Admin-Token")
	copyHeader(req.Header, incoming.Header, "X-Request-ID")
	req.Header.Set("X-TQuant-Bff-Hop", "1")
	if cfg.internalToken != "" {
		req.Header.Set("X-Internal-Service-Token", cfg.internalToken)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return nil, fmt.Errorf("source %s returned status %d", source.name, resp.StatusCode)
	}
	var raw json.RawMessage
	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		return nil, err
	}
	return raw, nil
}

func workspaceName(path string) string {
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) >= 4 && parts[len(parts)-2] == "workspace" {
		return parts[len(parts)-1]
	}
	return ""
}

func queryDefault(values url.Values, key string, fallback string) string {
	if value := strings.TrimSpace(values.Get(key)); value != "" {
		return value
	}
	return fallback
}

func values(items ...string) url.Values {
	output := url.Values{}
	for i := 0; i+1 < len(items); i += 2 {
		output.Set(items[i], items[i+1])
	}
	return output
}

func jsonPayload(status int, payload map[string]any) aggregateResult {
	body, err := json.Marshal(payload)
	if err != nil {
		return aggregateResult{}
	}
	return aggregateResult{
		status:      status,
		body:        body,
		contentType: "application/json; charset=utf-8",
		ok:          true,
	}
}

func nullableJSON(raw json.RawMessage) any {
	if len(raw) == 0 {
		return nil
	}
	return raw
}

func jsonArray(raw json.RawMessage) any {
	if len(raw) == 0 {
		return []any{}
	}
	return raw
}

func jsonObject(raw json.RawMessage) any {
	if len(raw) == 0 {
		return map[string]any{}
	}
	return raw
}

func jsonArrayField(raw json.RawMessage, field string) any {
	if len(raw) == 0 {
		return []any{}
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil {
		return []any{}
	}
	if value, ok := object[field]; ok && len(value) > 0 {
		return value
	}
	return []any{}
}

func beijingNowString() string {
	return time.Now().UTC().Add(8 * time.Hour).Format("2006-01-02T15:04:05+08:00")
}
