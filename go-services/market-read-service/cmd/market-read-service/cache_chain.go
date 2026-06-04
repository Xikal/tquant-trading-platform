package main

import (
	"context"
	"strings"
	"sync"
)

const unresolvedQuoteSampleLimit = 20

type unresolvedQuoteSample struct {
	Symbol string
	Reason string
}

var unresolvedQuoteSampleStore = struct {
	sync.Mutex
	values []unresolvedQuoteSample
}{}

type chainedQuoteCache struct {
	primary   quoteCache
	secondary quoteCache
}

func newMarketReadCache(redisURL string, databaseURL string) quoteCache {
	return chainedQuoteCache{
		primary:   newRedisQuoteCache(redisURL),
		secondary: newMySQLQuoteCache(databaseURL),
	}
}

func (cache chainedQuoteCache) Get(ctx context.Context, key string) ([]byte, error) {
	values, err := cache.MGet(ctx, []string{key})
	if err != nil {
		return nil, err
	}
	return values[key], nil
}

func (cache chainedQuoteCache) MGet(ctx context.Context, keys []string) (map[string][]byte, error) {
	result := make(map[string][]byte, len(keys))
	remaining := make([]string, 0, len(keys))
	if batch, ok := cache.primary.(quoteMultiCache); ok {
		if values, err := batch.MGet(ctx, keys); err == nil {
			for key, value := range values {
				if len(value) > 0 {
					result[key] = value
				}
			}
			marketReadRedisHits.Add(int64(len(result)))
		}
	}
	for _, key := range keys {
		if len(result[key]) == 0 {
			remaining = append(remaining, key)
		}
	}
	if len(remaining) == 0 {
		return result, nil
	}
	marketReadCacheMisses.Add(int64(len(remaining)))
	if batch, ok := cache.secondary.(quoteMultiCache); ok {
		if values, err := batch.MGet(ctx, remaining); err == nil {
			mysqlHits := 0
			for key, value := range values {
				if len(value) > 0 {
					result[key] = value
					mysqlHits++
				}
			}
			if mysqlHits > 0 {
				marketReadMySQLFallbacks.Add(int64(mysqlHits))
			}
		}
	}
	unresolved := 0
	for _, key := range remaining {
		if len(result[key]) == 0 {
			unresolved++
			recordUnresolvedQuoteSample(key, "mysql_fallback_missing")
		}
	}
	if unresolved > 0 {
		marketReadUnresolvedMisses.Add(int64(unresolved))
	}
	return result, nil
}

func recordUnresolvedQuoteSample(key string, reason string) {
	symbol := strings.TrimPrefix(strings.TrimSpace(key), quoteCachePrefix)
	if symbol == "" {
		return
	}
	cleanReason := boundedUnresolvedReason(reason)
	incrementUnresolvedReason(cleanReason)
	unresolvedQuoteSampleStore.Lock()
	defer unresolvedQuoteSampleStore.Unlock()
	for _, item := range unresolvedQuoteSampleStore.values {
		if item.Symbol == symbol {
			return
		}
	}
	unresolvedQuoteSampleStore.values = append(unresolvedQuoteSampleStore.values, unresolvedQuoteSample{Symbol: symbol, Reason: cleanReason})
	if len(unresolvedQuoteSampleStore.values) > unresolvedQuoteSampleLimit {
		unresolvedQuoteSampleStore.values = unresolvedQuoteSampleStore.values[len(unresolvedQuoteSampleStore.values)-unresolvedQuoteSampleLimit:]
	}
}

func unresolvedQuoteSamples() []string {
	samples := unresolvedQuoteReasonSamples()
	result := make([]string, len(samples))
	for index, item := range samples {
		result[index] = item.Symbol
	}
	return result
}

func unresolvedQuoteReasonSamples() []unresolvedQuoteSample {
	unresolvedQuoteSampleStore.Lock()
	defer unresolvedQuoteSampleStore.Unlock()
	values := make([]unresolvedQuoteSample, len(unresolvedQuoteSampleStore.values))
	copy(values, unresolvedQuoteSampleStore.values)
	return values
}

func unresolvedQuoteSamplePayload(missing []string, reasons map[string]string) []map[string]string {
	result := make([]map[string]string, 0, len(missing))
	seen := map[string]bool{}
	for _, symbol := range missing {
		clean := strings.TrimSpace(symbol)
		if clean == "" || seen[clean] {
			continue
		}
		seen[clean] = true
		result = append(result, map[string]string{
			"symbol": clean,
			"reason": boundedUnresolvedReason(reasons[clean]),
		})
		if len(result) >= unresolvedQuoteSampleLimit {
			return result
		}
	}
	return result
}

func boundedUnresolvedReason(reason string) string {
	switch reason {
	case "not_in_demand_set", "cache_write_failed", "cache_read_miss", "mysql_fallback_missing", "stale_quote", "schema_mismatch":
		return reason
	default:
		return "cache_read_miss"
	}
}

func incrementUnresolvedReason(reason string) {
	switch reason {
	case "not_in_demand_set":
		marketReadUnresolvedNotInDemandSet.Add(1)
	case "cache_write_failed":
		marketReadUnresolvedCacheWriteFailed.Add(1)
	case "cache_read_miss":
		marketReadUnresolvedCacheReadMiss.Add(1)
	case "mysql_fallback_missing":
		marketReadUnresolvedMySQLFallbackMissing.Add(1)
	case "stale_quote":
		marketReadUnresolvedStaleQuote.Add(1)
	case "schema_mismatch":
		marketReadUnresolvedSchemaMismatch.Add(1)
	}
}

func (cache chainedQuoteCache) MinuteBars(ctx context.Context, symbols []string, period string, limit int) (map[string][]map[string]any, error) {
	result := make(map[string][]map[string]any)
	if primary, ok := cache.primary.(minuteBarCache); ok {
		if values, err := primary.MinuteBars(ctx, symbols, period, limit); err == nil {
			for symbol, bars := range values {
				if len(bars) > 0 {
					result[symbol] = bars
				}
			}
		}
	}
	remaining := make([]string, 0, len(symbols))
	for _, symbol := range symbols {
		if len(result[symbol]) == 0 {
			remaining = append(remaining, symbol)
		}
	}
	if len(remaining) == 0 {
		return result, nil
	}
	if secondary, ok := cache.secondary.(minuteBarCache); ok {
		values, err := secondary.MinuteBars(ctx, remaining, period, limit)
		if err != nil {
			return result, nil
		}
		for symbol, bars := range values {
			if len(bars) > 0 {
				result[symbol] = bars
			}
		}
	}
	return result, nil
}
