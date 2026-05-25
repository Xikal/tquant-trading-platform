package main

import (
	"encoding/json"
	"errors"
	"net/http"
	"sort"
	"strings"
)

type sectorStrengthRequest struct {
	Sector  string                `json:"sector"`
	Symbols []string              `json:"symbols"`
	Sectors []sectorStrengthGroup `json:"sectors"`
	Limit   int                   `json:"limit"`
}

type sectorStrengthGroup struct {
	Sector  string   `json:"sector"`
	Symbols []string `json:"symbols"`
}

func sectorStrengthHandler(cache quoteCache) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		request, err := parseSectorStrengthRequest(r)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"detail": err.Error()})
			return
		}
		limit := request.Limit
		if limit <= 0 || limit > 50 {
			limit = 10
		}
		results := make([]map[string]any, 0, len(request.Sectors))
		totalMissing := 0
		totalItems := 0
		for _, group := range request.Sectors {
			result := buildSectorStrength(r, cache, group, limit)
			totalMissing += len(result.missing)
			totalItems += len(result.leaders)
			results = append(results, result.payload)
		}
		quality := "fresh"
		status := http.StatusOK
		if totalItems == 0 {
			quality = "unavailable"
			status = http.StatusServiceUnavailable
		} else if totalMissing > 0 {
			quality = "partial"
		}
		writeJSON(w, status, map[string]any{
			"source":       "redis_local_quote_cache",
			"data_quality": quality,
			"sectors":      results,
		})
	})
}

func parseSectorStrengthRequest(r *http.Request) (sectorStrengthRequest, error) {
	var request sectorStrengthRequest
	if r.Method == http.MethodPost {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			return request, errors.New("invalid JSON body")
		}
	}
	if request.Sector == "" {
		request.Sector = strings.TrimSpace(r.URL.Query().Get("sector"))
	}
	if len(request.Symbols) == 0 {
		request.Symbols = splitSymbols(r.URL.Query().Get("symbols"))
	}
	if len(request.Sectors) == 0 && request.Sector != "" && len(request.Symbols) > 0 {
		request.Sectors = []sectorStrengthGroup{{Sector: request.Sector, Symbols: request.Symbols}}
	}
	if len(request.Sectors) == 0 {
		return request, errors.New("sector and symbols are required")
	}
	return request, nil
}

func buildSectorStrength(r *http.Request, cache quoteCache, group sectorStrengthGroup, limit int) sectorResult {
	changeValues := make([]float64, 0, len(group.Symbols))
	quotes := make([]map[string]any, 0, len(group.Symbols))
	missing := make([]string, 0)
	for _, symbol := range dedupeSymbols(group.Symbols) {
		quote, ok := readCachedQuote(r.Context(), cache, symbol)
		if !ok {
			missing = append(missing, symbol)
			continue
		}
		quote["symbol"] = symbol
		quotes = append(quotes, quote)
		changeValues = append(changeValues, floatField(quote, "change_pct"))
	}
	medianChange := medianFloat(changeValues)
	leaders := make([]map[string]any, 0, len(quotes))
	for _, quote := range quotes {
		changePct := floatField(quote, "change_pct")
		volumeRatio := floatField(quote, "volume_ratio")
		turnoverRate := floatField(quote, "turnover_rate")
		score := (changePct-medianChange)*10 + volumeRatio*5 + turnoverRate
		leaders = append(leaders, map[string]any{
			"symbol":                 stringField(quote, "symbol"),
			"name":                   stringField(quote, "name"),
			"last_price":             roundFloat(floatField(quote, "last_price"), 4),
			"change_pct":             roundFloat(changePct, 4),
			"sector_median_change":   roundFloat(medianChange, 4),
			"relative_strength_diff": roundFloat(changePct-medianChange, 4),
			"volume_ratio":           roundFloat(volumeRatio, 4),
			"turnover_rate":          roundFloat(turnoverRate, 4),
			"leader_score":           roundFloat(score, 4),
			"data_quality":           stringField(quote, "data_quality"),
		})
	}
	sort.Slice(leaders, func(i, j int) bool {
		return floatField(leaders[i], "leader_score") > floatField(leaders[j], "leader_score")
	})
	if len(leaders) > limit {
		leaders = leaders[:limit]
	}
	return sectorResult{
		missing: missing,
		leaders: leaders,
		payload: map[string]any{
			"sector":               group.Sector,
			"median_change_pct":    roundFloat(medianChange, 4),
			"sample_size":          len(quotes),
			"missing":              missing,
			"leaders":              leaders,
			"calculation_note":     "leader_score = 相对板块涨幅差*10 + 量比*5 + 换手率；仅基于本地行情快照。",
			"production_writeable": false,
		},
	}
}

type sectorResult struct {
	payload map[string]any
	leaders []map[string]any
	missing []string
}

func splitSymbols(raw string) []string {
	return dedupeSymbols(strings.Split(raw, ","))
}

func dedupeSymbols(parts []string) []string {
	seen := map[string]bool{}
	symbols := make([]string, 0, len(parts))
	for _, part := range parts {
		symbol := strings.TrimSpace(part)
		if symbol == "" || seen[symbol] {
			continue
		}
		seen[symbol] = true
		symbols = append(symbols, symbol)
	}
	return symbols
}
