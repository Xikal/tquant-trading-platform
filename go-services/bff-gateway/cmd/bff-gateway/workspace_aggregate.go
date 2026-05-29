package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

const schemaVersion = "v15"

type aggregateResult struct {
	status      int
	body        []byte
	contentType string
	ok          bool
}

type partialError struct {
	Source    string `json:"source"`
	Reason    string `json:"reason"`
	Detail    string `json:"detail"`
	ElapsedMs int64  `json:"elapsed_ms,omitempty"`
}

type rawSource struct {
	name    string
	path    string
	query   url.Values
	timeout time.Duration
}

func aggregateWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	workspace := workspaceName(r.URL.Path)
	switch workspace {
	case "monitor":
		return aggregateMonitorWorkspace(cfg, client, r)
	case "paper":
		return aggregatePaperWorkspace(cfg, client, r)
	case "strategy":
		return aggregateStrategyWorkspace(cfg, client, r)
	case "strategy-tracking":
		return aggregateStrategyTrackingWorkspace(cfg, client, r)
	case "settings":
		return aggregateSettingsWorkspace(cfg, client, r)
	case "factor":
		return aggregateFactorWorkspace(cfg, client, r)
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
			"strategy_tracking": map[string]any{
				"path":           "/api/bff/v1/workspace/strategy-tracking",
				"schema_version": schemaVersion,
				"model":          "StrategyTrackingWorkspaceBffResponse",
			},
			"settings": map[string]any{"path": "/api/bff/v1/workspace/settings", "schema_version": schemaVersion, "model": "SettingsWorkspaceBffResponse"},
			"factor":   map[string]any{"path": "/api/bff/v1/workspace/factor", "schema_version": schemaVersion, "model": "FactorWorkspaceBffResponse"},
		},
	}
	return jsonPayload(http.StatusOK, payload)
}

func aggregateMonitorWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	q := r.URL.Query()
	sources := []rawSource{
		{name: "monitor_snapshot", path: "/api/monitor/snapshot", query: values("priority_limit", queryDefault(q, "priority_limit", "12"))},
		{name: "market_breadth", path: "/api/market/breadth", query: values("realtime", "true"), timeout: 250 * time.Millisecond},
		{name: "market_pulse", path: "/api/market/pulse"},
		{name: "monitor_review", path: "/api/market/review-summary"},
		{name: "sector_relative_strength", path: "/api/market/sector-relative-strength", query: values(
			"limit", queryDefault(q, "sector_limit", "8"),
			"per_sector_limit", queryDefault(q, "per_sector_limit", "8"),
		), timeout: 250 * time.Millisecond},
		{name: "paired_hedge", path: "/api/market/paired-hedge-research", query: values("limit", queryDefault(q, "hedge_limit", "4")), timeout: 250 * time.Millisecond},
	}
	results, errors := fetchSources(cfg, client, r, sources)
	payload := map[string]any{
		"api_version":              "v1",
		"schema_version":           schemaVersion,
		"generated_at":             beijingNowString(),
		"monitor_snapshot":         nullableJSON(results["monitor_snapshot"]),
		"market_breadth":           nullableJSON(results["market_breadth"]),
		"market_pulse":             nullableJSON(results["market_pulse"]),
		"review_status":            jsonObjectField(results["monitor_review"], "review_status"),
		"review_reports":           jsonArrayField(results["monitor_review"], "review_reports"),
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

func aggregateStrategyWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	q := r.URL.Query()
	sources := []rawSource{
		{name: "strategy_meta", path: "/api/strategies/meta"},
		{name: "presets", path: "/api/strategy/presets"},
		{name: "recent_runs", path: "/api/backtests", query: values("limit", queryDefault(q, "run_limit", "8"), "offset", "0")},
		{name: "verdict_thresholds", path: "/api/backtests/verdict-thresholds"},
		{name: "factor_health", path: "/api/factor-mining/health", query: values("limit", queryDefault(q, "factor_limit", "20"))},
	}
	results, errors := fetchSources(cfg, client, r, sources)
	payload := map[string]any{
		"api_version":        "v1",
		"schema_version":     schemaVersion,
		"generated_at":       beijingNowString(),
		"strategy_meta":      nullableJSON(results["strategy_meta"]),
		"presets":            nullableJSON(results["presets"]),
		"recent_runs":        nullableJSON(results["recent_runs"]),
		"verdict_thresholds": nullableJSON(results["verdict_thresholds"]),
		"factor_health":      nullableJSON(results["factor_health"]),
		"partial_errors":     errors,
	}
	return jsonPayload(http.StatusOK, payload)
}

func aggregateStrategyTrackingWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	q := r.URL.Query()
	rangeDays := queryDefault(q, "range", "30")
	summaryQuery := forwardQuery(q, []string{"strategy_key", "strategy_family", "status"}, values("range", rangeDays))
	itemsQuery := forwardQuery(
		q,
		[]string{"strategy_key", "strategy_family", "status", "signal_state", "data_quality", "hit_entry", "stopped"},
		values(
			"range", rangeDays,
			"sort", queryDefault(q, "sort", "max_gain_desc"),
			"limit", queryDefault(q, "limit", "30"),
			"offset", queryDefault(q, "offset", "0"),
		),
	)
	performanceQuery := forwardQuery(q, []string{"strategy_family"}, values("range", rangeDays))
	sources := []rawSource{
		{name: "strategy_tracking_summary", path: "/api/strategy-tracking/summary", query: summaryQuery},
		{name: "strategy_tracking_items", path: "/api/strategy-tracking/items", query: itemsQuery},
		{name: "strategy_tracking_performance", path: "/api/strategy-tracking/performance", query: performanceQuery},
	}
	detailID := strings.TrimSpace(q.Get("detail_id"))
	if detailID != "" {
		sources = append(sources, rawSource{
			name: "strategy_tracking_detail",
			path: "/api/strategy-tracking/items/" + url.PathEscape(detailID),
		})
	}
	results, errors := fetchSources(cfg, client, r, sources)
	payload := map[string]any{
		"api_version":          "v1",
		"schema_version":       schemaVersion,
		"generated_at":         beijingNowString(),
		"summary":              jsonObject(results["strategy_tracking_summary"]),
		"items":                jsonArrayField(results["strategy_tracking_items"], "items"),
		"total":                jsonObjectField(results["strategy_tracking_items"], "total"),
		"limit":                jsonObjectField(results["strategy_tracking_items"], "limit"),
		"offset":               jsonObjectField(results["strategy_tracking_items"], "offset"),
		"sort":                 jsonObjectField(results["strategy_tracking_items"], "sort"),
		"performance":          jsonArray(results["strategy_tracking_performance"]),
		"detail":               nullableJSON(results["strategy_tracking_detail"]),
		"detail_requested":     detailID != "",
		"partial_errors":       errors,
		"production_writeable": false,
		"read_path":            "go_bff_strategy_tracking_read_aggregation",
	}
	return jsonPayload(http.StatusOK, payload)
}

func aggregateSettingsWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	q := r.URL.Query()
	includeAdmin := strings.EqualFold(queryDefault(q, "include_admin", "false"), "true")
	sources := []rawSource{
		{name: "settings", path: "/api/settings"},
		{name: "sector_exclusions", path: "/api/settings/sector-exclusions"},
		{name: "strategy_governance", path: "/api/screeners/low-buy/strategies"},
	}
	if includeAdmin {
		sources = append(sources,
			rawSource{name: "runtime", path: "/api/settings/runtime"},
			rawSource{name: "factor_weights", path: "/api/settings/factor-weights"},
			rawSource{name: "admin_tasks", path: "/api/admin/tasks"},
			rawSource{name: "admin_metrics", path: "/api/admin/metrics"},
		)
	}
	results, errors := fetchSources(cfg, client, r, sources)
	payload := map[string]any{
		"api_version":         "v1",
		"schema_version":      schemaVersion,
		"generated_at":        beijingNowString(),
		"settings":            nullableJSON(results["settings"]),
		"sector_exclusions":   nullableJSON(results["sector_exclusions"]),
		"strategy_governance": nullableJSON(results["strategy_governance"]),
		"runtime":             nullableJSON(results["runtime"]),
		"factor_weights":      nullableJSON(results["factor_weights"]),
		"admin_tasks":         nullableJSON(results["admin_tasks"]),
		"admin_metrics":       nullableJSON(results["admin_metrics"]),
		"admin_enabled":       includeAdmin,
		"partial_errors":      errors,
	}
	return jsonPayload(http.StatusOK, payload)
}

func aggregateFactorWorkspace(cfg config, client *http.Client, r *http.Request) aggregateResult {
	q := r.URL.Query()
	sources := []rawSource{
		{name: "factors", path: "/api/factor-mining/factors", query: values("limit", queryDefault(q, "factor_limit", "50"), "offset", "0")},
		{name: "factor_health", path: "/api/factor-mining/health", query: values("limit", queryDefault(q, "health_limit", "50"))},
		{name: "factor_weights", path: "/api/settings/factor-weights"},
	}
	results, errors := fetchSources(cfg, client, r, sources)
	payload := map[string]any{
		"api_version":    "v1",
		"schema_version": schemaVersion,
		"generated_at":   beijingNowString(),
		"factors":        nullableJSON(results["factors"]),
		"factor_health":  nullableJSON(results["factor_health"]),
		"factor_weights": nullableJSON(results["factor_weights"]),
		"partial_errors": errors,
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
			started := time.Now()
			body, err := fetchRawSource(cfg, client, r, source)
			elapsedMs := time.Since(started).Milliseconds()
			mu.Lock()
			defer mu.Unlock()
			if err != nil {
				bffPartialSourceFailures.Add(1)
				reason := partialReason(err)
				incrementPartialReason(reason)
				errors = append(errors, partialError{Source: source.name, Reason: reason, Detail: partialDetail(err, resolvedSourceTimeout(cfg, source)), ElapsedMs: elapsedMs})
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
	ctx, cancel := context.WithTimeout(incoming.Context(), resolvedSourceTimeout(cfg, source))
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target.String(), nil)
	if err != nil {
		return nil, err
	}
	copyHeader(req.Header, incoming.Header, "Authorization")
	copyHeader(req.Header, incoming.Header, "X-Admin-Token")
	copyHeader(req.Header, incoming.Header, "X-Request-ID")
	copyHeader(req.Header, incoming.Header, "traceparent")
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

func partialReason(err error) string {
	if err == nil {
		return "other"
	}
	text := strings.ToLower(err.Error())
	switch {
	case strings.Contains(text, "deadline exceeded"):
		return "timeout"
	case strings.Contains(text, "returned status"):
		return "status"
	case strings.Contains(text, "invalid character") || strings.Contains(text, "json"):
		return "decode"
	default:
		return "other"
	}
}

func incrementPartialReason(reason string) {
	switch reason {
	case "timeout":
		bffPartialTimeoutFailures.Add(1)
	case "status":
		bffPartialStatusFailures.Add(1)
	case "decode":
		bffPartialDecodeFailures.Add(1)
	default:
		bffPartialOtherFailures.Add(1)
	}
}

func partialDetail(err error, timeout time.Duration) string {
	if err == nil {
		return "数据暂时不可用"
	}
	if strings.Contains(strings.ToLower(err.Error()), "deadline exceeded") {
		return fmt.Sprintf("source timeout after %dms", timeout.Milliseconds())
	}
	return "数据暂时不可用"
}

func resolvedSourceTimeout(cfg config, source rawSource) time.Duration {
	if source.timeout > 0 {
		return source.timeout
	}
	if cfg.sourceTimeout > 0 {
		return cfg.sourceTimeout
	}
	return time.Second
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

func forwardQuery(source url.Values, keys []string, output url.Values) url.Values {
	for _, key := range keys {
		if value := strings.TrimSpace(source.Get(key)); value != "" {
			output.Set(key, value)
		}
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

func jsonObjectField(raw json.RawMessage, field string) any {
	if len(raw) == 0 {
		return nil
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(raw, &object); err != nil {
		return nil
	}
	if value, ok := object[field]; ok && len(value) > 0 {
		return value
	}
	return nil
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
