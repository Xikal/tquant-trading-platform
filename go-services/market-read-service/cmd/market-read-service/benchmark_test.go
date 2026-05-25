package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func BenchmarkQuoteBatchHandlerCachedPayload(b *testing.B) {
	cache := mapQuoteCache{
		"tquant:market:quote:000001": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000001","last_price":10.12,"change_pct":1.2,"open_price":10.0,"high_price":10.3,"low_price":9.9,"prev_close":9.8,"volume":1000,"amount":10000}}`),
		"tquant:market:quote:000002": []byte(`{"cached_at":4102444800,"payload":{"symbol":"000002","last_price":8.65,"change_pct":-0.5,"open_price":8.7,"high_price":8.8,"low_price":8.5,"prev_close":8.7,"volume":1500,"amount":12000}}`),
	}
	handler := quoteBatchHandler(cache)
	req := httptest.NewRequest(http.MethodGet, "/api/market-read/v1/quote-batch?symbols=000001,000002", nil)

	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, req)
		if recorder.Code != http.StatusOK {
			b.Fatalf("unexpected status: %d body=%s", recorder.Code, recorder.Body.String())
		}
		if !strings.Contains(recorder.Body.String(), `"data_quality":"fresh"`) {
			b.Fatalf("unexpected body: %s", recorder.Body.String())
		}
	}
}
