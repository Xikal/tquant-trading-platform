package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestHealthHandler(t *testing.T) {
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)

	health(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
}

func TestReadEndpointsExposeProductionReadiness(t *testing.T) {
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/market-read/v1/quote-batch", nil)

	notEnabled(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
	if !bytes.Contains(recorder.Body.Bytes(), []byte(`"production_readiness":"mainline_ready"`)) {
		t.Fatalf("expected production readiness in body: %s", recorder.Body.String())
	}
}

func TestInternalOnlyRejectsMissingToken(t *testing.T) {
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/market-read/v1/quote-batch", nil)
	handler := internalOnly("internal-secret", http.HandlerFunc(notEnabled))

	handler.ServeHTTP(recorder, req)

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

func TestQuoteBatchReadsRedisLocalQuotePayload(t *testing.T) {
	cache := mapQuoteCache{
		"tquant:market:quote:000001": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000001","last_price":10.12}}`),
	}
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/market-read/v1/quote-batch?symbols=000001,000002", nil)

	quoteBatchHandler(cache).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
	var payload map[string]any
	if err := json.Unmarshal(recorder.Body.Bytes(), &payload); err != nil {
		t.Fatalf("invalid json response: %v", err)
	}
	if payload["data_quality"] != "partial" {
		t.Fatalf("data quality mismatch: %v", payload["data_quality"])
	}
	items := payload["items"].([]any)
	if len(items) != 1 {
		t.Fatalf("items length mismatch got=%d", len(items))
	}
}

func TestIntradayLatestMarksExpiredCacheStale(t *testing.T) {
	cache := mapQuoteCache{
		"tquant:market:quote:000001": []byte(`{"cached_at":1,"payload":{"symbol":"000001","last_price":10.12}}`),
	}
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/market-read/v1/intraday-latest-batch?symbols=000001", nil)

	intradayLatestBatchHandler(cache).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
	var payload map[string]any
	if err := json.Unmarshal(recorder.Body.Bytes(), &payload); err != nil {
		t.Fatalf("invalid json response: %v", err)
	}
	items := payload["items"].([]any)
	first := items[0].(map[string]any)
	if first["data_quality"] != "stale" {
		t.Fatalf("expected stale quality, got %v", first["data_quality"])
	}
	if age, _ := first["age_seconds"].(float64); age < float64(24*time.Hour/time.Second) {
		t.Fatalf("expected old cache age, got %v", first["age_seconds"])
	}
}

func TestIntradayLatestPreservesStaleQualityEvenWhenRecentlyCached(t *testing.T) {
	cache := mapQuoteCache{
		"tquant:market:quote:000001": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000001","last_price":10.12,"data_quality":"stale","source_quality":"stale","is_stale":true}}`),
	}
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/market-read/v1/intraday-latest-batch?symbols=000001", nil)

	intradayLatestBatchHandler(cache).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
	var payload map[string]any
	if err := json.Unmarshal(recorder.Body.Bytes(), &payload); err != nil {
		t.Fatalf("invalid json response: %v", err)
	}
	items := payload["items"].([]any)
	first := items[0].(map[string]any)
	if first["data_quality"] != "stale" {
		t.Fatalf("expected stale quality, got %v", first["data_quality"])
	}
	latest := first["latest"].(map[string]any)
	if latest["data_quality"] != "stale" || latest["is_stale"] != true {
		t.Fatalf("expected stale latest payload, got %#v", latest)
	}
}

func TestMySQLDSNParsesSQLAlchemyURL(t *testing.T) {
	dsn := mysqlDSN("mysql+pymysql://user:pass@mysql:3306/tquant")

	if dsn != "user:pass@tcp(mysql:3306)/tquant?parseTime=true&charset=utf8mb4" {
		t.Fatalf("dsn mismatch: %s", dsn)
	}
}

func TestIntradayKeyLevelsUseCachedQuote(t *testing.T) {
	cache := mapQuoteCache{
		"tquant:market:quote:000001": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000001","name":"平安银行","last_price":10.12,"open_price":10,"prev_close":9.9}}`),
	}
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/market-read/v1/intraday-key-levels?symbol=000001&entry_zone_low=10.1&entry_zone_high=10.3", nil)

	intradayKeyLevelsHandler(cache).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
	var payload map[string]any
	if err := json.Unmarshal(recorder.Body.Bytes(), &payload); err != nil {
		t.Fatalf("invalid json response: %v", err)
	}
	levels := payload["levels"].([]any)
	if len(levels) == 0 {
		t.Fatalf("expected key levels")
	}
	if payload["entry_zone_low"] != 10.1 {
		t.Fatalf("expected entry_zone_low echo, got %v", payload["entry_zone_low"])
	}
	if payload["entry_zone_high"] != 10.3 {
		t.Fatalf("expected entry_zone_high echo, got %v", payload["entry_zone_high"])
	}
}

func TestSectorStrengthRanksCachedQuotes(t *testing.T) {
	cache := mapQuoteCache{
		"tquant:market:quote:000001": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000001","name":"平安银行","last_price":10.12,"change_pct":1.5,"volume_ratio":2,"turnover_rate":1}}`),
		"tquant:market:quote:000002": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000002","name":"万科A","last_price":7.5,"change_pct":0.2,"volume_ratio":1,"turnover_rate":0.8}}`),
	}
	body := bytes.NewBufferString(`{"sector":"测试板块","symbols":["000001","000002"],"limit":2}`)
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/market-read/v1/sector-relative-strength", body)

	sectorStrengthHandler(cache).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
	var payload map[string]any
	if err := json.Unmarshal(recorder.Body.Bytes(), &payload); err != nil {
		t.Fatalf("invalid json response: %v", err)
	}
	sectors := payload["sectors"].([]any)
	firstSector := sectors[0].(map[string]any)
	leaders := firstSector["leaders"].([]any)
	top := leaders[0].(map[string]any)
	if top["symbol"] != "000001" {
		t.Fatalf("top leader mismatch: %v", top["symbol"])
	}
}

func TestIntradayLatestBatchHandlerReturnsPartialPayload(t *testing.T) {
	cache := mapQuoteCache{
		"tquant:market:quote:000001": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000001","last_price":10.1,"change_pct":1.2,"timestamp":"2026-05-25 10:00:00"}}`),
	}
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/market-read/v1/intraday-latest-batch?symbols=000001,000002", nil)

	intradayLatestBatchHandler(cache).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d body=%s", http.StatusOK, recorder.Code, recorder.Body.String())
	}
	if !bytes.Contains(recorder.Body.Bytes(), []byte(`"data_quality":"partial"`)) {
		t.Fatalf("expected partial quality body=%s", recorder.Body.String())
	}
	if !bytes.Contains(recorder.Body.Bytes(), []byte(`"latest"`)) {
		t.Fatalf("expected latest payload body=%s", recorder.Body.String())
	}
}

func TestChainedQuoteCacheRecordsRedisMissAndMySQLFallbackMetrics(t *testing.T) {
	redis := mapQuoteCache{
		"tquant:market:quote:000001": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000001","last_price":10.1}}`),
	}
	mysql := mapQuoteCache{
		"tquant:market:quote:000002": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000002","last_price":9.8,"data_source":"mysql_daily_bar_snapshot"}}`),
	}
	cache := chainedQuoteCache{primary: redis, secondary: mysql}
	beforeRedis := marketReadRedisHits.Load()
	beforeMisses := marketReadCacheMisses.Load()
	beforeMySQL := marketReadMySQLFallbacks.Load()

	values, err := cache.MGet(
		nil,
		[]string{
			"tquant:market:quote:000001",
			"tquant:market:quote:000002",
			"tquant:market:quote:000003",
		},
	)

	if err != nil {
		t.Fatalf("MGet returned error: %v", err)
	}
	if len(values["tquant:market:quote:000001"]) == 0 || len(values["tquant:market:quote:000002"]) == 0 {
		t.Fatalf("expected redis and mysql payloads, got %#v", values)
	}
	if marketReadRedisHits.Load()-beforeRedis != 1 {
		t.Fatalf("expected one redis hit")
	}
	if marketReadCacheMisses.Load()-beforeMisses != 2 {
		t.Fatalf("expected two primary cache misses")
	}
	if marketReadMySQLFallbacks.Load()-beforeMySQL != 1 {
		t.Fatalf("expected one mysql fallback hit")
	}
}

func TestMetricsExposeCacheCoverageCounters(t *testing.T) {
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)

	metrics(recorder, req)

	body := recorder.Body.String()
	for _, metricName := range []string{
		"tquant_market_read_redis_hits_total",
		"tquant_market_read_cache_miss_total",
		"tquant_market_read_mysql_fallbacks_total",
	} {
		if !bytes.Contains([]byte(body), []byte(metricName)) {
			t.Fatalf("metrics should expose %s, body=%s", metricName, body)
		}
	}
}
