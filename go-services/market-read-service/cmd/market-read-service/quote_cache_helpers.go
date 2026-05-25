package main

import (
	"context"
	"encoding/json"
	"math"
	"sort"
	"strconv"
)

func readCachedQuote(ctx context.Context, cache quoteCache, symbol string) (map[string]any, bool) {
	raw, err := cache.Get(ctx, quoteCachePrefix+symbol)
	if err != nil || len(raw) == 0 {
		return nil, false
	}
	item, err := parseQuoteCachePayload(symbol, raw)
	if err != nil {
		return nil, false
	}
	quote, _ := item["quote"].(map[string]any)
	return quote, quote != nil
}

func floatField(payload map[string]any, key string) float64 {
	value, ok := payload[key]
	if !ok || value == nil {
		return 0
	}
	switch typed := value.(type) {
	case float64:
		return typed
	case float32:
		return float64(typed)
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case json.Number:
		parsed, _ := typed.Float64()
		return parsed
	case string:
		parsed, _ := strconv.ParseFloat(typed, 64)
		return parsed
	default:
		return 0
	}
}

func stringField(payload map[string]any, key string) string {
	value, _ := payload[key].(string)
	return value
}

func roundFloat(value float64, places int) float64 {
	factor := math.Pow(10, float64(places))
	return math.Round(value*factor) / factor
}

func medianFloat(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	copied := append([]float64(nil), values...)
	sort.Float64s(copied)
	mid := len(copied) / 2
	if len(copied)%2 == 1 {
		return copied[mid]
	}
	return (copied[mid-1] + copied[mid]) / 2
}
