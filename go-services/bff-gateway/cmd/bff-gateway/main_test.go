package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestWorkspaceTargetURLAddsApiPrefixForShortPath(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/bff/v1/workspace/paper?order_limit=5", nil)

	target, err := workspaceTargetURL("http://python:8000", req)

	if err != nil {
		t.Fatalf("workspaceTargetURL returned error: %v", err)
	}
	want := "http://python:8000/api/bff/v1/workspace/paper?order_limit=5"
	if target != want {
		t.Fatalf("target mismatch want=%s got=%s", want, target)
	}
}

func TestMonitorAggregateReturnsPartialWhenPulseIsSlow(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/monitor/snapshot":
			_, _ = w.Write([]byte(`{"updated_at":"2026-05-27 10:00:00","watchlist_signals":[],"priority_board":{"items":[]}}`))
		case "/api/market/pulse":
			time.Sleep(250 * time.Millisecond)
			_, _ = w.Write([]byte(`{"pulse_text":"late"}`))
		default:
			_, _ = w.Write([]byte(`{}`))
		}
	}))
	defer upstream.Close()

	cfg := config{
		pythonAPIBase: upstream.URL,
		internalToken: "token",
		sourceTimeout: 50 * time.Millisecond,
	}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/monitor", nil)
	result := aggregateMonitorWorkspace(cfg, upstream.Client(), req)

	if result.status != http.StatusOK {
		t.Fatalf("expected ok, got %d", result.status)
	}
	if !bytes.Contains(result.body, []byte(`"source":"market_pulse"`)) {
		t.Fatalf("expected pulse partial error: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"monitor_snapshot"`)) {
		t.Fatalf("expected snapshot to remain present: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`source timeout after 50ms`)) {
		t.Fatalf("expected timeout detail: %s", string(result.body))
	}
}

func TestMonitorAggregateUsesShortDeadlineForHeavyOptionalSources(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/monitor/snapshot":
			_, _ = w.Write([]byte(`{"updated_at":"2026-05-27 10:00:00","watchlist_signals":[],"priority_board":{"items":[]}}`))
		case "/api/market/breadth", "/api/market/sector-relative-strength", "/api/market/paired-hedge-research":
			time.Sleep(700 * time.Millisecond)
			_, _ = w.Write([]byte(`{"late":true}`))
		default:
			_, _ = w.Write([]byte(`{}`))
		}
	}))
	defer upstream.Close()

	cfg := config{
		pythonAPIBase: upstream.URL,
		internalToken: "token",
		sourceTimeout: 900 * time.Millisecond,
	}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/monitor", nil)
	started := time.Now()
	result := aggregateMonitorWorkspace(cfg, upstream.Client(), req)

	if result.status != http.StatusOK {
		t.Fatalf("expected ok, got %d", result.status)
	}
	if elapsed := time.Since(started); elapsed >= 600*time.Millisecond {
		t.Fatalf("expected heavy optional sources to short-timeout, elapsed=%s body=%s", elapsed, string(result.body))
	}
	for _, source := range []string{"market_breadth", "sector_relative_strength", "paired_hedge"} {
		if !bytes.Contains(result.body, []byte(`"source":"`+source+`"`)) {
			t.Fatalf("expected %s partial error: %s", source, string(result.body))
		}
	}
	if !bytes.Contains(result.body, []byte(`source timeout after 250ms`)) {
		t.Fatalf("expected short timeout detail: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"monitor_snapshot"`)) {
		t.Fatalf("expected snapshot to remain present: %s", string(result.body))
	}
}

func TestWorkspaceTargetURLKeepsApiPath(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/strategy?run_limit=3", nil)

	target, err := workspaceTargetURL("http://python:8000", req)

	if err != nil {
		t.Fatalf("workspaceTargetURL returned error: %v", err)
	}
	want := "http://python:8000/api/bff/v1/workspace/strategy?run_limit=3"
	if target != want {
		t.Fatalf("target mismatch want=%s got=%s", want, target)
	}
}

func TestManifestTargetURLAddsApiPrefixForShortPath(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/bff/v1/manifest", nil)

	target, err := workspaceTargetURL("http://python:8000", req)

	if err != nil {
		t.Fatalf("workspaceTargetURL returned error: %v", err)
	}
	want := "http://python:8000/api/bff/v1/manifest"
	if target != want {
		t.Fatalf("target mismatch want=%s got=%s", want, target)
	}
}

func TestProxyWorkspaceRejectsMissingInternalToken(t *testing.T) {
	cfg := config{
		pythonAPIBase: "http://python:8000",
		internalToken: "internal-secret",
		timeout:       time.Second,
	}
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/paper", nil)

	proxyWorkspaceHandler(cfg, http.DefaultClient, newWorkspaceCache(time.Second)).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusForbidden {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusForbidden, recorder.Code)
	}
}

func TestValidateInternalTokenRejectsProductionEmptyToken(t *testing.T) {
	t.Setenv("APP_ENVIRONMENT", "production")

	if err := validateInternalToken(""); err != errMissingProductionInternalToken {
		t.Fatalf("expected missing token error, got %v", err)
	}
}

func TestValidateInternalTokenAllowsDevelopmentEmptyToken(t *testing.T) {
	t.Setenv("APP_ENVIRONMENT", "development")

	if err := validateInternalToken(""); err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
}

func TestDurationSecondsAcceptsNumberAndDurationSyntax(t *testing.T) {
	t.Setenv("TEST_TIMEOUT_SECONDS", "2.5")
	if got := durationSeconds("TEST_TIMEOUT_SECONDS", 5); got != 2500*time.Millisecond {
		t.Fatalf("numeric seconds mismatch got=%s", got)
	}

	t.Setenv("TEST_TIMEOUT_SECONDS", "750ms")
	if got := durationSeconds("TEST_TIMEOUT_SECONDS", 5); got != 750*time.Millisecond {
		t.Fatalf("duration syntax mismatch got=%s", got)
	}
}

func TestRequestIDMiddlewareWritesGeneratedIDToRequestAndResponse(t *testing.T) {
	var seenRequestID string
	var seenTraceparent string
	handler := requestIDMiddleware(http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) {
		seenRequestID = r.Header.Get("X-Request-ID")
		seenTraceparent = r.Header.Get("traceparent")
	}))
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)

	handler.ServeHTTP(recorder, req)

	if seenRequestID == "" {
		t.Fatal("expected generated request id on proxied request")
	}
	if recorder.Header().Get("X-Request-ID") != seenRequestID {
		t.Fatalf("response request id mismatch got=%s want=%s", recorder.Header().Get("X-Request-ID"), seenRequestID)
	}
	if seenTraceparent == "" {
		t.Fatal("expected generated traceparent on proxied request")
	}
	if recorder.Header().Get("traceparent") != seenTraceparent {
		t.Fatalf("response traceparent mismatch got=%s want=%s", recorder.Header().Get("traceparent"), seenTraceparent)
	}
}

func TestRequestIDMiddlewarePreservesIncomingTraceparent(t *testing.T) {
	incomingTraceparent := "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
	var seenTraceparent string
	handler := requestIDMiddleware(http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) {
		seenTraceparent = r.Header.Get("traceparent")
	}))
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	req.Header.Set("traceparent", incomingTraceparent)

	handler.ServeHTTP(recorder, req)

	if seenTraceparent != incomingTraceparent {
		t.Fatalf("request traceparent mismatch got=%s want=%s", seenTraceparent, incomingTraceparent)
	}
	if recorder.Header().Get("traceparent") != incomingTraceparent {
		t.Fatalf("response traceparent mismatch got=%s want=%s", recorder.Header().Get("traceparent"), incomingTraceparent)
	}
}

func TestWorkspaceCacheReturnsFreshEntryAndExpires(t *testing.T) {
	cache := newWorkspaceCache(25 * time.Millisecond)
	cache.set("key", http.StatusOK, []byte(`{"ok":true}`), "application/json")

	item, ok := cache.get("key")
	if !ok {
		t.Fatal("expected cache hit")
	}
	if item.status != http.StatusOK {
		t.Fatalf("unexpected cached status %d", item.status)
	}
	if !bytes.Equal(item.body, []byte(`{"ok":true}`)) {
		t.Fatalf("unexpected cached body %q", string(item.body))
	}
	time.Sleep(35 * time.Millisecond)
	if _, ok := cache.get("key"); ok {
		t.Fatal("expected cache item to expire")
	}
	if got := cache.size(); got != 0 {
		t.Fatalf("expected expired cache size 0 got=%d", got)
	}
	if got := cache.ttlSeconds(); got <= 0 {
		t.Fatalf("expected positive ttl got=%f", got)
	}
}

func TestWorkspaceCacheKeyUsesIdentityAndQuery(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/paper?run_limit=3", nil)
	req.Header.Set("Authorization", "Bearer a")
	req.Header.Set("X-Admin-Token", "admin")

	key := workspaceCacheKey(req)

	if key == "" {
		t.Fatal("expected cache key")
	}
	req2 := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/paper?run_limit=4", nil)
	req2.Header.Set("Authorization", "Bearer a")
	req2.Header.Set("X-Admin-Token", "admin")
	if key == workspaceCacheKey(req2) {
		t.Fatal("expected cache key to vary by query")
	}
}

func TestAggregateManifestReturnsLocalContract(t *testing.T) {
	result := aggregateManifest()

	if !result.ok {
		t.Fatal("expected local manifest aggregate result")
	}
	assertJSONField(t, result.body, "schema_version", schemaVersion)
	if !bytes.Contains(result.body, []byte(`"paper"`)) {
		t.Fatalf("manifest should include paper workspace: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"strategy_tracking"`)) {
		t.Fatalf("manifest should include strategy tracking workspace: %s", string(result.body))
	}
}

func TestAggregatePaperWorkspaceBuildsPayloadFromSourceEndpoints(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-TQuant-Bff-Hop") != "1" {
			t.Fatalf("expected BFF hop header")
		}
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/paper/account":
			_, _ = w.Write([]byte(`{"id":7,"name":"默认模拟账户"}`))
		case "/api/paper/positions":
			_, _ = w.Write([]byte(`{"positions":[{"symbol":"510300"}],"total_market_value":100}`))
		case "/api/paper/orders":
			if got := r.URL.Query().Get("limit"); got != "3" {
				t.Fatalf("order limit mismatch got=%s", got)
			}
			_, _ = w.Write([]byte(`[{"id":1}]`))
		case "/api/paper/trades":
			_, _ = w.Write([]byte(`{"trades":[{"id":9}]}`))
		case "/api/paper/performance/stock-pnl":
			_, _ = w.Write([]byte(`{"items":[]}`))
		case "/api/paper/performance":
			_, _ = w.Write([]byte(`{"total_return_pct":1.2}`))
		case "/api/paper/performance/sector-etf-t0":
			_, _ = w.Write([]byte(`{"sample_count":0}`))
		case "/api/paper/performance/by-strategy", "/api/paper/performance/by-market-state", "/api/paper/performance/by-tag":
			_, _ = w.Write([]byte(`[]`))
		case "/api/paper/risk/events":
			_, _ = w.Write([]byte(`[]`))
		case "/api/paper/auto-trading/status":
			_, _ = w.Write([]byte(`{"running":false}`))
		case "/api/paper/auto-trading/runs":
			_, _ = w.Write([]byte(`[]`))
		default:
			t.Fatalf("unexpected upstream path %s", r.URL.Path)
		}
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, timeout: time.Second}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/paper?order_limit=3", nil)

	result := aggregatePaperWorkspace(cfg, upstream.Client(), req)

	if !result.ok {
		t.Fatal("expected paper aggregate result")
	}
	assertJSONField(t, result.body, "schema_version", schemaVersion)
	if !bytes.Contains(result.body, []byte(`"account":{"id":7`)) {
		t.Fatalf("paper aggregate missing account: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"positions":[{"symbol":"510300"}]`)) {
		t.Fatalf("paper aggregate missing positions: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"partial_errors":[]`)) {
		t.Fatalf("paper aggregate should not report partial errors: %s", string(result.body))
	}
}

func TestMetricsExposeCacheAndWorkspaceDimensions(t *testing.T) {
	cache := newWorkspaceCache(2 * time.Second)
	cache.set("key", http.StatusOK, []byte(`{"ok":true}`), "application/json")
	bffCacheLookups.Store(4)
	bffCacheHits.Store(1)
	bffWorkspaceAggregateStrategyHits.Store(2)
	bffWorkspaceProxySettingsFallbacks.Store(1)
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)

	metricsHandler(cache).ServeHTTP(recorder, req)

	body := recorder.Body.String()
	if !bytes.Contains([]byte(body), []byte("tquant_bff_gateway_cache_items 1")) {
		t.Fatalf("metrics missing cache item count: %s", body)
	}
	if !bytes.Contains([]byte(body), []byte("tquant_bff_gateway_cache_hit_rate 0.250000")) {
		t.Fatalf("metrics missing cache hit rate: %s", body)
	}
	if !bytes.Contains([]byte(body), []byte(`tquant_bff_gateway_workspace_aggregate_hits_total{workspace="strategy"} 2`)) {
		t.Fatalf("metrics missing strategy aggregate dimension: %s", body)
	}
	if !bytes.Contains([]byte(body), []byte(`tquant_bff_gateway_workspace_proxy_fallbacks_total{workspace="settings"} 1`)) {
		t.Fatalf("metrics missing settings proxy dimension: %s", body)
	}
	for _, reason := range []string{"timeout", "status", "decode", "other"} {
		if !bytes.Contains([]byte(body), []byte(`tquant_bff_gateway_partial_source_failures_total{reason="`+reason+`"}`)) {
			t.Fatalf("metrics missing partial reason %s: %s", reason, body)
		}
	}
}

func TestAggregateMonitorWorkspaceIncludesPulseAndReview(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/monitor/snapshot":
			_, _ = w.Write([]byte(`{"updated_at":"2026-05-25 10:00:00","watchlist_signals":[],"priority_board":{"items":[]}}`))
		case "/api/market/breadth":
			_, _ = w.Write([]byte(`{"updated_at":"2026-05-25 10:00:00","state":"repair","data_quality":"fresh"}`))
		case "/api/market/pulse":
			_, _ = w.Write([]byte(`{"updated_at":"2026-05-25 10:00:00","data_quality":"partial","pulse_text":"盘中结构转为可观察","suggested_action":"控制追高"}`))
		case "/api/market/review-summary":
			_, _ = w.Write([]byte(`{"review_status":{"trade_date":"2026-05-25","status":"midday_ready","status_text":"今日市场午盘复盘已生成，等待收盘复盘","review_subject":"全市场","source_scope":"market","has_midday":true,"has_close":false,"next_trigger_at":"2026-05-25 15:05","risk_alert_count":1,"suggested_action":"午后控制追高"},"review_reports":[{"id":1,"report_slot":"midday","review_subject":"全市场","source_scope":"market","suggestion":"午后控制追高"}]}`))
		case "/api/market/sector-relative-strength":
			_, _ = w.Write([]byte(`{"updated_at":"2026-05-25 10:00:00","items":[]}`))
		case "/api/market/paired-hedge-research":
			_, _ = w.Write([]byte(`{"updated_at":"2026-05-25 10:00:00","ideas":[]}`))
		default:
			t.Fatalf("unexpected upstream path %s", r.URL.Path)
		}
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, timeout: time.Second}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/monitor?priority_limit=3", nil)

	result := aggregateMonitorWorkspace(cfg, upstream.Client(), req)

	if !result.ok {
		t.Fatal("expected monitor aggregate result")
	}
	assertJSONField(t, result.body, "schema_version", schemaVersion)
	if !bytes.Contains(result.body, []byte(`"market_pulse":{"updated_at"`)) {
		t.Fatalf("monitor aggregate missing market_pulse: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"review_status":{"trade_date":"2026-05-25"`)) {
		t.Fatalf("monitor aggregate missing review_status: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"review_reports":[{"id":1`)) {
		t.Fatalf("monitor aggregate missing review reports: %s", string(result.body))
	}
}

func TestAggregateStrategyWorkspaceBuildsPayloadFromSourceEndpoints(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/strategies/meta":
			_, _ = w.Write([]byte(`{"strategies":[{"key":"first_board","display_name":"首板"}]}`))
		case "/api/strategy/presets":
			_, _ = w.Write([]byte(`{"presets":[{"preset_key":"default","name":"默认"}]}`))
		case "/api/backtests":
			if got := r.URL.Query().Get("limit"); got != "4" {
				t.Fatalf("run limit mismatch got=%s", got)
			}
			_, _ = w.Write([]byte(`{"items":[{"id":1}],"total":1}`))
		case "/api/backtests/verdict-thresholds":
			_, _ = w.Write([]byte(`{"thresholds":{"light":{"min_return_pct":1}}}`))
		case "/api/factor-mining/health":
			_, _ = w.Write([]byte(`{"total":0,"items":[]}`))
		default:
			t.Fatalf("unexpected upstream path %s", r.URL.Path)
		}
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, timeout: time.Second}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/strategy?run_limit=4", nil)

	result := aggregateStrategyWorkspace(cfg, upstream.Client(), req)

	if !result.ok {
		t.Fatal("expected strategy aggregate result")
	}
	if !bytes.Contains(result.body, []byte(`"strategy_meta":{"strategies"`)) {
		t.Fatalf("strategy aggregate missing metadata: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"factor_health":{"total":0`)) {
		t.Fatalf("strategy aggregate missing factor health: %s", string(result.body))
	}
}

func TestAggregateStrategyTrackingWorkspaceBuildsReadOnlyPayload(t *testing.T) {
	snapshotRequests := 0
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/strategy-tracking/snapshot":
			snapshotRequests++
			if got := r.URL.Query().Get("range"); got != "20" {
				t.Fatalf("snapshot range mismatch got=%s", got)
			}
			if got := r.URL.Query().Get("strategy_family"); got != "core" {
				t.Fatalf("snapshot strategy_family mismatch got=%s", got)
			}
			if got := r.URL.Query().Get("strategy_key"); got != "first_board_pullback" {
				t.Fatalf("snapshot strategy_key mismatch got=%s", got)
			}
			if got := r.URL.Query().Get("hit_entry"); got != "true" {
				t.Fatalf("snapshot hit_entry mismatch got=%s", got)
			}
			if got := r.URL.Query().Get("exclude_chinext"); got != "true" {
				t.Fatalf("snapshot exclude_chinext mismatch got=%s", got)
			}
			if got := r.URL.Query().Get("exclude_star"); got != "true" {
				t.Fatalf("snapshot exclude_star mismatch got=%s", got)
			}
			if got := r.URL.Query().Get("limit"); got != "30" {
				t.Fatalf("snapshot limit mismatch got=%s", got)
			}
			_, _ = w.Write([]byte(`{"status":"fresh","stale":false,"generated_at":"2026-05-29T10:00:00+08:00","source_data_cutoff":"2026-05-29T09:30:00+08:00","data_version":"2026-05-29:2026-05-29T09:30:00:1","snapshot_key":"strategy-tracking:test","payload":{"summary":{"tracking_count":2,"active_count":1,"today_new_count":0,"in_entry_zone_count":1,"stopped_count":0,"needs_review_count":1,"abnormal_return_count":0,"shadow_observation_count":0,"avg_current_return_pct":1.2,"median_max_gain_pct":4.5,"data_quality":"ok","data_quality_text":"数据完整","generated_at":"2026-05-29T10:00:00+08:00"},"items":[{"id":"first_board_pullback:600000:2026-05-28","symbol":"600000","best_holding_days":3,"needs_review":true}],"performance":[{"strategy_key":"first_board_pullback","recommendation_count":2,"health_score":70}],"holding_summary":{"items":[{"strategy_key":"first_board_pullback","sample_count":2,"dominant_holding_bucket_text":"短线 1-3 天"}],"generated_at":"2026-05-29T10:00:00+08:00","data_quality":"ok","production_writeable":false},"market_segments":[{"strategy_key":"first_board_pullback","market_state":"strong_market","recommendation_count":2}],"shadow_observations":[{"model_key":"main_force_model_observation","observation_count":0,"no_sample_reason":"no_model_observation"}],"audit":{"future_leak_check":"passed","checked_count":1,"violation_count":0,"abnormal_return_count":0,"needs_review_count":1,"audit_flags":[]}},"total":1,"limit":30,"offset":0,"sort":"max_gain_desc","partial_errors":[],"production_writeable":false,"read_path":"strategy_tracking_snapshot","notes":[]}`))
		case "/api/strategy-tracking/items/first_board_pullback:600000:2026-05-28":
			_, _ = w.Write([]byte(`{"item":{"id":"first_board_pullback:600000:2026-05-28"},"timeline":[],"markers":[],"signal_snapshot":{},"review_text":"ok","partial_errors":[],"production_writeable":false}`))
		default:
			t.Fatalf("unexpected upstream path %s", r.URL.Path)
		}
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, timeout: time.Second}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/strategy-tracking?range=20&strategy_family=core&strategy_key=first_board_pullback&hit_entry=true&exclude_chinext=true&exclude_star=true&detail_id=first_board_pullback:600000:2026-05-28", nil)

	result := aggregateStrategyTrackingWorkspace(cfg, upstream.Client(), req)

	if !result.ok {
		t.Fatal("expected strategy tracking aggregate result")
	}
	if snapshotRequests != 1 {
		t.Fatalf("expected one snapshot request, got %d", snapshotRequests)
	}
	assertJSONField(t, result.body, "schema_version", schemaVersion)
	if !bytes.Contains(result.body, []byte(`"snapshot_status":"fresh"`)) {
		t.Fatalf("strategy tracking aggregate missing snapshot status: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"summary":{"tracking_count":2`)) {
		t.Fatalf("strategy tracking aggregate missing summary: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"items":[{"id":"first_board_pullback:600000:2026-05-28"`)) {
		t.Fatalf("strategy tracking aggregate missing items: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"performance":[{"strategy_key":"first_board_pullback"`)) {
		t.Fatalf("strategy tracking aggregate missing performance: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"holding_analysis":{"items":[{"strategy_key":"first_board_pullback"`)) {
		t.Fatalf("strategy tracking aggregate missing holding analysis: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"market_segments":[{"strategy_key":"first_board_pullback"`)) {
		t.Fatalf("strategy tracking aggregate missing market segments: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"shadow_observations":[{"model_key":"main_force_model_observation"`)) {
		t.Fatalf("strategy tracking aggregate missing shadow observations: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"production_writeable":false`)) {
		t.Fatalf("strategy tracking aggregate should remain read-only: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"detail":{"item":{"id":"first_board_pullback:600000:2026-05-28"`)) {
		t.Fatalf("strategy tracking aggregate missing optional detail: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"detail_requested":true`)) {
		t.Fatalf("strategy tracking aggregate should mark detail request: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"read_path":"go_bff_strategy_tracking_snapshot_aggregation"`)) {
		t.Fatalf("strategy tracking aggregate should expose snapshot read path: %s", string(result.body))
	}
}

func TestAggregateStrategyTrackingWorkspaceReportsSnapshotTimeout(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/strategy-tracking/snapshot":
			time.Sleep(120 * time.Millisecond)
			_, _ = w.Write([]byte(`{"status":"fresh","payload":{"items":[]}}`))
		default:
			t.Fatalf("unexpected upstream path %s", r.URL.Path)
		}
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, sourceTimeout: 50 * time.Millisecond}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/strategy-tracking?range=20", nil)

	result := aggregateStrategyTrackingWorkspace(cfg, upstream.Client(), req)

	if result.status != http.StatusOK {
		t.Fatalf("expected ok, got %d", result.status)
	}
	if !bytes.Contains(result.body, []byte(`"items":[]`)) {
		t.Fatalf("strategy tracking aggregate should keep an empty fast-path payload when snapshot times out: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"source":"strategy_tracking_snapshot"`)) {
		t.Fatalf("strategy tracking aggregate should report snapshot partial error: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"reason":"timeout"`)) {
		t.Fatalf("strategy tracking aggregate should report snapshot timeout: %s", string(result.body))
	}
}

func TestAggregateSettingsWorkspaceBuildsAdminPayload(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/settings":
			_, _ = w.Write([]byte(`{"database_url":"sqlite:///app.db"}`))
		case "/api/settings/sector-exclusions":
			_, _ = w.Write([]byte(`{"items":[]}`))
		case "/api/screeners/low-buy/strategies":
			_, _ = w.Write([]byte(`{"items":[]}`))
		case "/api/settings/runtime":
			_, _ = w.Write([]byte(`{"database_backend":"sqlite"}`))
		case "/api/settings/factor-weights":
			_, _ = w.Write([]byte(`{"items":[]}`))
		case "/api/admin/tasks":
			_, _ = w.Write([]byte(`{"queued":0}`))
		case "/api/admin/metrics":
			_, _ = w.Write([]byte(`{"ok":true}`))
		default:
			t.Fatalf("unexpected upstream path %s", r.URL.Path)
		}
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, timeout: time.Second}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/settings?include_admin=true", nil)

	result := aggregateSettingsWorkspace(cfg, upstream.Client(), req)

	if !result.ok {
		t.Fatal("expected settings aggregate result")
	}
	if !bytes.Contains(result.body, []byte(`"admin_enabled":true`)) {
		t.Fatalf("settings aggregate missing admin flag: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"runtime":{"database_backend":"sqlite"`)) {
		t.Fatalf("settings aggregate missing runtime: %s", string(result.body))
	}
}

func TestAggregateFactorWorkspaceBuildsPayload(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/factor-mining/factors":
			_, _ = w.Write([]byte(`{"items":[{"factor_key":"demo","name":"演示"}],"total":1}`))
		case "/api/factor-mining/health":
			_, _ = w.Write([]byte(`{"total":1,"items":[{"factor_key":"demo"}]}`))
		case "/api/settings/factor-weights":
			_, _ = w.Write([]byte(`{"items":[]}`))
		default:
			t.Fatalf("unexpected upstream path %s", r.URL.Path)
		}
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, timeout: time.Second}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/factor", nil)

	result := aggregateFactorWorkspace(cfg, upstream.Client(), req)

	if !result.ok {
		t.Fatal("expected factor aggregate result")
	}
	if !bytes.Contains(result.body, []byte(`"factors":{"items":[{"factor_key":"demo"`)) {
		t.Fatalf("factor aggregate missing factors: %s", string(result.body))
	}
}

func TestAggregateMonitorWorkspacePartialFailureIsObservable(t *testing.T) {
	bffPartialSourceFailures.Store(0)
	bffPartialStatusFailures.Store(0)
	resetPartialSourceReasonFailures()
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/market/review-summary":
			http.Error(w, "review unavailable", http.StatusBadGateway)
		default:
			_, _ = w.Write([]byte(`{}`))
		}
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, timeout: time.Second}
	req := httptest.NewRequest(http.MethodGet, "/api/bff/v1/workspace/monitor", nil)

	result := aggregateMonitorWorkspace(cfg, upstream.Client(), req)

	if !result.ok {
		t.Fatal("expected monitor aggregate result")
	}
	if !bytes.Contains(result.body, []byte(`"source":"monitor_review"`)) {
		t.Fatalf("monitor aggregate should report review partial error: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"reason":"status"`)) {
		t.Fatalf("monitor aggregate should report partial reason: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"status_code":502`)) {
		t.Fatalf("monitor aggregate should report partial status code: %s", string(result.body))
	}
	if !bytes.Contains(result.body, []byte(`"fallback_source":"go_bff_gateway"`)) {
		t.Fatalf("monitor aggregate should report fallback source: %s", string(result.body))
	}
	if bffPartialSourceFailures.Load() == 0 {
		t.Fatal("expected partial source failure metric to increment")
	}
	if bffPartialStatusFailures.Load() == 0 {
		t.Fatal("expected status partial source failure metric to increment")
	}
	lines := strings.Join(partialSourceReasonMetricsLines(), "\n")
	if !strings.Contains(lines, `tquant_bff_gateway_partial_source_failures_total{source="monitor_review",reason="status"} 1`) {
		t.Fatalf("missing source/reason metric: %s", lines)
	}
}

func TestPartialReasonClassifiesTimeoutStatusAndDecode(t *testing.T) {
	if got := partialReason(context.DeadlineExceeded); got != "timeout" {
		t.Fatalf("timeout reason mismatch: %s", got)
	}
	if got := partialReason(errors.New("source market_pulse returned status 502")); got != "status" {
		t.Fatalf("status reason mismatch: %s", got)
	}
	if got := partialReason(errors.New("invalid character '<' looking for beginning of value")); got != "decode" {
		t.Fatalf("decode reason mismatch: %s", got)
	}
}

func assertJSONField(t *testing.T, body []byte, field string, want string) {
	t.Helper()
	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		t.Fatalf("invalid json: %v", err)
	}
	if got := payload[field]; got != want {
		t.Fatalf("%s mismatch want=%s got=%v", field, want, got)
	}
}
