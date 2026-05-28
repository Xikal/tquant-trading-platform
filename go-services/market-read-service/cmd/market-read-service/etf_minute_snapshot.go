package main

import (
	"context"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"
)

const minuteCachePrefix = "tquant:market:minute:"

type minuteBarCache interface {
	MinuteBars(context.Context, []string, string, int) (map[string][]map[string]any, error)
}

func etfMinuteSnapshotBatchHandler(cache quoteCache) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		symbols, err := parseQuoteSymbols(r)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"detail": err.Error()})
			return
		}
		period := strings.TrimSpace(r.URL.Query().Get("period"))
		if period == "" {
			period = "1m"
		}
		if period != "1m" && period != "5m" && period != "15m" {
			writeJSON(w, http.StatusBadRequest, map[string]any{"detail": "period must be 1m, 5m or 15m"})
			return
		}
		limit := parseLimit(r.URL.Query().Get("limit"), 30, 240)
		provider, ok := cache.(minuteBarCache)
		if !ok {
			writeJSON(w, http.StatusServiceUnavailable, map[string]any{
				"source":       "go_market_read_service",
				"data_quality": "unavailable",
				"items":        []any{},
				"missing":      symbols,
				"detail":       "minute bar cache not configured",
			})
			marketReadFallbacks.Add(1)
			return
		}
		values, _ := provider.MinuteBars(r.Context(), symbols, period, limit)
		items := make([]map[string]any, 0, len(symbols))
		missing := make([]string, 0)
		staleCount := 0
		for _, symbol := range symbols {
			bars := values[symbol]
			if len(bars) == 0 {
				missing = append(missing, symbol)
				continue
			}
			item := buildMinuteSnapshotItem(symbol, period, bars)
			if item["data_quality"] == "stale" {
				staleCount++
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
		} else if staleCount > 0 {
			quality = "stale"
			marketReadPartials.Add(1)
			marketReadHits.Add(1)
		} else {
			marketReadHits.Add(1)
		}
		writeJSON(w, status, map[string]any{
			"source":       "redis_mysql_minute_bar_snapshot",
			"period":       period,
			"data_quality": quality,
			"items":        items,
			"missing":      missing,
		})
	})
}

func buildMinuteSnapshotItem(symbol string, period string, bars []map[string]any) map[string]any {
	sort.SliceStable(bars, func(i, j int) bool {
		return stringField(bars[i], "timestamp") < stringField(bars[j], "timestamp")
	})
	latest := bars[len(bars)-1]
	totalAmount := 0.0
	high := 0.0
	low := 0.0
	for _, bar := range bars {
		totalAmount += floatField(bar, "amount")
		barHigh := floatField(bar, "high")
		barLow := floatField(bar, "low")
		if barHigh > high {
			high = barHigh
		}
		if low == 0 || (barLow > 0 && barLow < low) {
			low = barLow
		}
	}
	latestTimestamp := stringField(latest, "timestamp")
	quality := "fresh"
	ageSeconds := minuteSnapshotAgeSeconds(latestTimestamp)
	if ageSeconds > 20*60 {
		quality = "stale"
	}
	return map[string]any{
		"symbol":            symbol,
		"period":            period,
		"bar_count":         len(bars),
		"latest_timestamp":  latestTimestamp,
		"latest_price":      floatField(latest, "close"),
		"latest_amount":     floatField(latest, "amount"),
		"total_amount":      totalAmount,
		"high_price":        high,
		"low_price":         low,
		"age_seconds":       ageSeconds,
		"data_quality":      quality,
		"bars":              bars,
		"strategy_decision": "none",
		"note":              "Go 只读分钟快照和数据质量；ETF 做T 信号仍由 Python 生成。",
	}
}

func parseLimit(raw string, fallback int, maxValue int) int {
	value, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil || value <= 0 {
		return fallback
	}
	if value > maxValue {
		return maxValue
	}
	return value
}

func minuteSnapshotAgeSeconds(timestamp string) float64 {
	if timestamp == "" {
		return 1e9
	}
	for _, layout := range []string{"2006-01-02 15:04:05", "2006-01-02 15:04"} {
		parsed, err := time.ParseInLocation(layout, timestamp, time.Local)
		if err == nil {
			return time.Since(parsed).Seconds()
		}
	}
	return 1e9
}
