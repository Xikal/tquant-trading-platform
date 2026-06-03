package main

import "net/http"

func intradayLatestBatchHandler(cache quoteCache) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		symbols, err := parseQuoteSymbols(r)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"detail": err.Error()})
			return
		}
		cachedPayloads := readQuotePayloads(r.Context(), cache, symbols)
		items := make([]map[string]any, 0, len(symbols))
		missing := make([]string, 0)
		unresolvedReasons := make(map[string]string)
		for _, symbol := range symbols {
			raw := cachedPayloads[symbol]
			if len(raw) == 0 {
				missing = append(missing, symbol)
				unresolvedReasons[symbol] = "not_in_cache"
				continue
			}
			item, err := parseQuoteCachePayload(symbol, raw)
			if err != nil {
				missing = append(missing, symbol)
				unresolvedReasons[symbol] = "not_in_cache"
				continue
			}
			quote, _ := item["quote"].(map[string]any)
			items = append(items, map[string]any{
				"symbol":       symbol,
				"latest":       quote,
				"cached_at":    item["cached_at"],
				"age_seconds":  item["age_seconds"],
				"data_quality": item["data_quality"],
			})
		}
		status := http.StatusOK
		quality := "fresh"
		if len(items) == 0 {
			status = http.StatusServiceUnavailable
			quality = "unavailable"
			marketReadFallbacks.Add(1)
		} else if len(missing) > 0 {
			quality = "partial"
			marketReadPartials.Add(1)
			marketReadHits.Add(1)
		} else {
			marketReadHits.Add(1)
		}
		writeJSON(w, status, map[string]any{
			"source":       "redis_mysql_quote_cache",
			"data_quality": quality,
			"items":        items,
			"missing":      missing,
			"unresolved_symbols_sample": unresolvedQuoteSamplePayload(
				missing,
				unresolvedReasons,
			),
		})
	})
}
