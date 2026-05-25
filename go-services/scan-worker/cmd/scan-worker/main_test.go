package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestShadowStatusNeverEnablesProductionWrites(t *testing.T) {
	t.Setenv("GO_SCAN_SHADOW_ENABLED", "true")
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/shadow/status", nil)

	shadowStatus(recorder, req)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusOK, recorder.Code)
	}
	body := recorder.Body.String()
	if !strings.Contains(body, `"shadow_enabled":true`) {
		t.Fatalf("expected shadow_enabled true in body: %s", body)
	}
	if !strings.Contains(body, `"production_write_enabled":false`) {
		t.Fatalf("expected production writes disabled in body: %s", body)
	}
	if !strings.Contains(body, `"production_scan_enabled":true`) {
		t.Fatalf("expected production read-only scan enabled in body: %s", body)
	}
	if !strings.Contains(body, `"production_readiness":"mainline_ready_readonly"`) {
		t.Fatalf("expected production readiness in body: %s", body)
	}
}

func TestInternalOnlyRejectsMissingToken(t *testing.T) {
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/shadow/status", nil)
	handler := internalOnly("internal-secret", http.HandlerFunc(shadowStatus))

	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusForbidden {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusForbidden, recorder.Code)
	}
}

func TestShadowRunRejectsWhenDisabled(t *testing.T) {
	t.Setenv("GO_SCAN_SHADOW_ENABLED", "false")
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/shadow/run?strategy=demo&limit=12", nil)

	shadowRun(recorder, req)

	if recorder.Code != http.StatusServiceUnavailable {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusServiceUnavailable, recorder.Code)
	}
}

func TestShadowRunAcceptedWhenEnabled(t *testing.T) {
	t.Setenv("GO_SCAN_SHADOW_ENABLED", "true")
	recorder := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/scan-worker/v1/shadow/run?strategy=demo&limit=12", nil)

	shadowRun(recorder, req)

	if recorder.Code != http.StatusAccepted {
		t.Fatalf("status mismatch want=%d got=%d", http.StatusAccepted, recorder.Code)
	}
	body := recorder.Body.String()
	if !strings.Contains(body, `"production_write_enabled":false`) {
		t.Fatalf("expected production writes disabled in body: %s", body)
	}
	if !strings.Contains(body, `"production_scan_enabled":true`) {
		t.Fatalf("expected production scan enabled in body: %s", body)
	}
	if !strings.Contains(body, `"strategy":"demo"`) {
		t.Fatalf("expected strategy in body: %s", body)
	}
}
