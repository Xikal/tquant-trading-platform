package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"time"
)

const quoteCachePrefix = "tquant:market:quote:"

type quoteBatchRequest struct {
	Symbols []string `json:"symbols"`
}

func quoteBatchHandler(cache quoteCache) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		symbols, err := parseQuoteSymbols(r)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"detail": err.Error()})
			return
		}
		cachedPayloads := readQuotePayloads(r.Context(), cache, symbols)
		items := make([]map[string]any, 0, len(symbols))
		missing := make([]string, 0)
		for _, symbol := range symbols {
			raw := cachedPayloads[symbol]
			if len(raw) == 0 {
				missing = append(missing, symbol)
				continue
			}
			item, err := parseQuoteCachePayload(symbol, raw)
			if err != nil {
				missing = append(missing, symbol)
				continue
			}
			items = append(items, item)
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
			"source":       "redis_local_quote_cache",
			"data_quality": quality,
			"items":        items,
			"missing":      missing,
		})
	})
}

type quoteMultiCache interface {
	MGet(context.Context, []string) (map[string][]byte, error)
}

func readQuotePayloads(ctx context.Context, cache quoteCache, symbols []string) map[string][]byte {
	keys := make([]string, 0, len(symbols))
	keyToSymbol := make(map[string]string, len(symbols))
	for _, symbol := range symbols {
		key := quoteCachePrefix + symbol
		keys = append(keys, key)
		keyToSymbol[key] = symbol
	}
	if batchCache, ok := cache.(quoteMultiCache); ok {
		rawByKey, err := batchCache.MGet(ctx, keys)
		if err == nil {
			rawBySymbol := make(map[string][]byte, len(rawByKey))
			for key, raw := range rawByKey {
				if symbol := keyToSymbol[key]; symbol != "" {
					rawBySymbol[symbol] = raw
				}
			}
			return rawBySymbol
		}
	}
	rawBySymbol := make(map[string][]byte, len(symbols))
	for _, symbol := range symbols {
		raw, err := cache.Get(ctx, quoteCachePrefix+symbol)
		if err == nil && len(raw) > 0 {
			rawBySymbol[symbol] = raw
		}
	}
	return rawBySymbol
}

func parseQuoteSymbols(r *http.Request) ([]string, error) {
	raw := r.URL.Query().Get("symbols")
	if raw == "" && r.Method == http.MethodPost {
		defer r.Body.Close()
		var payload quoteBatchRequest
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			return nil, errors.New("invalid JSON body")
		}
		raw = strings.Join(payload.Symbols, ",")
	}
	seen := map[string]bool{}
	symbols := make([]string, 0)
	for _, part := range strings.Split(raw, ",") {
		symbol := strings.TrimSpace(part)
		if symbol == "" || seen[symbol] {
			continue
		}
		seen[symbol] = true
		symbols = append(symbols, symbol)
	}
	if len(symbols) == 0 {
		return nil, errors.New("symbols is required")
	}
	if len(symbols) > 1000 {
		return nil, errors.New("symbols limit is 1000")
	}
	return symbols, nil
}

func parseQuoteCachePayload(symbol string, raw []byte) (map[string]any, error) {
	var payload map[string]any
	if err := json.Unmarshal(raw, &payload); err != nil {
		return nil, err
	}
	cachedAt, _ := payload["cached_at"].(float64)
	quote, _ := payload["payload"].(map[string]any)
	if quote == nil {
		quote = payload
	}
	if quote["symbol"] == nil {
		quote["symbol"] = symbol
	}
	age := 0.0
	quality := "fresh"
	if cachedAt > 0 {
		age = time.Since(time.Unix(int64(cachedAt), 0)).Seconds()
		if age > 15 {
			quality = "stale"
		}
	}
	return map[string]any{
		"symbol":       symbol,
		"quote":        quote,
		"cached_at":    cachedAt,
		"age_seconds":  age,
		"data_quality": quality,
	}, nil
}

type mapQuoteCache map[string][]byte

func (cache mapQuoteCache) Get(_ context.Context, key string) ([]byte, error) {
	if value, ok := cache[key]; ok {
		return value, nil
	}
	return nil, nil
}

func (cache mapQuoteCache) MGet(_ context.Context, keys []string) (map[string][]byte, error) {
	result := make(map[string][]byte, len(keys))
	for _, key := range keys {
		if value, ok := cache[key]; ok {
			result[key] = value
		}
	}
	return result, nil
}
