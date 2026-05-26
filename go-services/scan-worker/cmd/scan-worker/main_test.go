package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestStatusEnablesProductionScanAndWrites(t *testing.T) {
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/status", nil)

	statusHandler(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
	body := recorder.Body.String()
	if !strings.Contains(body, `"production_scan_enabled":true`) {
		t.Fatalf("expected production scan enabled in body: %s", body)
	}
	if !strings.Contains(body, `"production_write_enabled":true`) {
		t.Fatalf("expected production writes enabled in body: %s", body)
	}
	if !strings.Contains(body, `"production_readiness":"python_reference_orchestrator"`) {
		t.Fatalf("expected python reference readiness in body: %s", body)
	}
	if !strings.Contains(body, `"strategy_engine":"python_reference"`) {
		t.Fatalf("expected strategy engine in body: %s", body)
	}
	if !strings.Contains(body, `"scan_worker_role":"go_orchestrated_reference"`) {
		t.Fatalf("expected scan worker role in body: %s", body)
	}
	if !strings.Contains(body, `"ranking_consistency"`) || !strings.Contains(body, `Python reference strategy engine`) {
		t.Fatalf("expected python reference ranking detail in body: %s", body)
	}
}

func TestInternalOnlyRejectsMissingToken(t *testing.T) {
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/status", nil)
	handler := internalOnly("internal-secret", http.HandlerFunc(statusHandler))

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

func TestRunCallsPythonReferenceAndReturnsWriteEnabledPayload(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/internal/scan-worker/v1/run" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		if r.Header.Get("X-Internal-Service-Token") != "internal-secret" {
			t.Fatalf("missing internal token")
		}
		if r.URL.Query().Get("strategies") != "demo,volume" {
			t.Fatalf("strategies mismatch got=%s", r.URL.Query().Get("strategies"))
		}
		_, _ = w.Write([]byte(`{"ok":true,"refreshed":["demo:2026-05-25"],"skipped":[]}`))
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, internalToken: "internal-secret", timeout: time.Second}
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/run?strategies=demo,volume&limit=12&scan_limit=72", nil)

	runHandler(cfg, upstream.Client()).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d body=%s", http.StatusOK, recorder.Code, recorder.Body.String())
	}
	body := recorder.Body.String()
	if !strings.Contains(body, `"production_write_enabled":true`) {
		t.Fatalf("expected production writes enabled in body: %s", body)
	}
	if !strings.Contains(body, `"scan_worker_source":"go_orchestrated_reference"`) {
		t.Fatalf("expected source in body: %s", body)
	}
	if !strings.Contains(body, `"strategy_engine":"python_reference"`) {
		t.Fatalf("expected strategy engine in body: %s", body)
	}
}

func TestRunReportsFallbackOnPythonFailure(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer upstream.Close()
	cfg := config{pythonAPIBase: upstream.URL, internalToken: "internal-secret", timeout: time.Second}
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/run?strategy=demo&limit=12", nil)

	runHandler(cfg, upstream.Client()).ServeHTTP(recorder, req)

	if recorder.Code != http.StatusBadGateway {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusBadGateway, recorder.Code)
	}
	body := recorder.Body.String()
	if !strings.Contains(body, `"fallback_available":true`) {
		t.Fatalf("expected fallback available in body: %s", body)
	}
	if !strings.Contains(body, `"production_write_enabled":false`) {
		t.Fatalf("expected failed run to disable writes in body: %s", body)
	}
	if !strings.Contains(body, `"strategy_engine":"python_reference"`) {
		t.Fatalf("expected strategy engine in body: %s", body)
	}
}
