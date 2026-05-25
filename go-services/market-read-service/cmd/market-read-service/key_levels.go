package main

import (
	"errors"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"
)

func intradayKeyLevelsHandler(cache quoteCache) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		symbol := strings.TrimSpace(r.URL.Query().Get("symbol"))
		if symbol == "" {
			writeJSON(w, http.StatusBadRequest, map[string]any{"detail": "symbol is required"})
			return
		}
		quote, ok := readCachedQuote(r.Context(), cache, symbol)
		if !ok {
			writeJSON(w, http.StatusServiceUnavailable, map[string]any{
				"symbol":       symbol,
				"source":       "redis_local_quote_cache",
				"data_quality": "unavailable",
				"detail":       "quote cache unavailable",
			})
			return
		}
		response, err := buildKeyLevelsResponse(symbol, quote, r)
		if err != nil {
			writeJSON(w, http.StatusServiceUnavailable, map[string]any{
				"symbol":       symbol,
				"source":       "redis_local_quote_cache",
				"data_quality": "unavailable",
				"detail":       err.Error(),
			})
			return
		}
		writeJSON(w, http.StatusOK, response)
	})
}

func buildKeyLevelsResponse(symbol string, quote map[string]any, r *http.Request) (map[string]any, error) {
	latestPrice := floatField(quote, "last_price")
	if latestPrice <= 0 {
		return nil, errors.New("latest price unavailable")
	}
	thresholdPct := parseQueryFloat(r, "threshold_pct", 0.3)
	levels := buildKeyLevels(
		latestPrice,
		floatField(quote, "vwap"),
		floatField(quote, "open_price"),
		floatField(quote, "prev_close"),
		parseQueryFloat(r, "entry_zone_low", 0),
		parseQueryFloat(r, "entry_zone_high", 0),
		thresholdPct,
	)
	alerts := make([]map[string]any, 0)
	for _, level := range levels {
		if alert, _ := level["alert"].(bool); alert {
			alerts = append(alerts, level)
		}
	}
	alertText := ""
	if len(alerts) > 0 {
		alertText = symbol + " 接近" + stringField(alerts[0], "level_text")
	}
	return map[string]any{
		"source":             "redis_local_quote_cache",
		"data_quality":       "partial",
		"data_quality_text":  "Go 读服务基于本地行情快照计算关键位；VWAP 仅在缓存字段存在时返回。",
		"symbol":             symbol,
		"name":               stringField(quote, "name"),
		"updated_at":         time.Now().Format(time.RFC3339),
		"latest_price":       roundFloat(latestPrice, 4),
		"vwap":               roundFloat(floatField(quote, "vwap"), 4),
		"alert_threshold_pct": thresholdPct,
		"alert_triggered":    len(alerts) > 0,
		"alert_text":         alertText,
		"levels":             levels,
	}, nil
}

func buildKeyLevels(latestPrice, vwap, openPrice, prevClose, entryLow, entryHigh, thresholdPct float64) []map[string]any {
	raw := []struct {
		levelType string
		text      string
		price     float64
	}{
		{"vwap", "分时均价 VWAP", vwap},
		{"open", "开盘价", openPrice},
		{"prev_close", "昨收", prevClose},
		{"entry_low", "买点区下沿", entryLow},
		{"entry_high", "买点区上沿", entryHigh},
	}
	for _, price := range roundNumberLevels(latestPrice) {
		raw = append(raw, struct {
			levelType string
			text      string
			price     float64
		}{"round_number", "整数关口", price})
	}
	seen := map[string]bool{}
	levels := make([]map[string]any, 0, len(raw))
	for _, item := range raw {
		if item.price <= 0 {
			continue
		}
		key := item.levelType + ":" + strconv.FormatFloat(roundFloat(item.price, 3), 'f', 3, 64)
		if seen[key] {
			continue
		}
		seen[key] = true
		distancePct := (latestPrice - item.price) / math.Max(item.price, 0.01) * 100
		levels = append(levels, map[string]any{
			"level_type":   item.levelType,
			"level_text":   item.text,
			"price":        roundFloat(item.price, 4),
			"distance_pct": roundFloat(distancePct, 4),
			"alert":        math.Abs(distancePct) <= thresholdPct,
		})
	}
	return levels
}

func roundNumberLevels(price float64) []float64 {
	step := 1.0
	if price < 20 {
		step = 0.5
	}
	lower := math.Floor(price/step) * step
	upper := math.Ceil(price/step) * step
	if lower == upper {
		return []float64{roundFloat(lower, 2)}
	}
	return []float64{roundFloat(lower, 2), roundFloat(upper, 2)}
}

func parseQueryFloat(r *http.Request, key string, fallback float64) float64 {
	raw := strings.TrimSpace(r.URL.Query().Get(key))
	if raw == "" {
		return fallback
	}
	parsed, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return fallback
	}
	return parsed
}
