package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
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
	handler := requestIDMiddleware(http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) {
		seenRequestID = r.Header.Get("X-Request-ID")
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
