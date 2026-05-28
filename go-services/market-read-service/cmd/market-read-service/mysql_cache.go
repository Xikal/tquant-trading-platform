package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net/url"
	"sort"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

type mysqlQuoteCache struct {
	db *sql.DB
}

func newMySQLQuoteCache(rawURL string) quoteCache {
	dsn := mysqlDSN(rawURL)
	if dsn == "" {
		return unavailableCache{}
	}
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return unavailableCache{}
	}
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(2)
	db.SetConnMaxLifetime(5 * time.Minute)
	return mysqlQuoteCache{db: db}
}

func (cache mysqlQuoteCache) Get(ctx context.Context, key string) ([]byte, error) {
	values, err := cache.MGet(ctx, []string{key})
	if err != nil {
		return nil, err
	}
	return values[key], nil
}

func (cache mysqlQuoteCache) MGet(ctx context.Context, keys []string) (map[string][]byte, error) {
	symbols := symbolsFromKeys(keys)
	if len(symbols) == 0 {
		return map[string][]byte{}, nil
	}
	query, args := latestDailyQuoteQuery(symbols)
	rows, err := cache.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := make(map[string][]byte, len(symbols))
	for rows.Next() {
		payload, err := scanDailyQuotePayload(rows)
		if err != nil {
			continue
		}
		raw, err := json.Marshal(payload)
		if err != nil {
			continue
		}
		symbol, _ := payload["payload"].(map[string]any)["symbol"].(string)
		if symbol != "" {
			result[quoteCachePrefix+symbol] = raw
		}
	}
	return result, rows.Err()
}

func (cache mysqlQuoteCache) MinuteBars(ctx context.Context, symbols []string, period string, limit int) (map[string][]map[string]any, error) {
	cleaned := dedupeSymbols(symbols)
	if len(cleaned) == 0 {
		return map[string][]map[string]any{}, nil
	}
	query, args := latestMinuteBarsQuery(cleaned, period, limit)
	rows, err := cache.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := make(map[string][]map[string]any, len(cleaned))
	for rows.Next() {
		var symbol, timestamp string
		var openPrice, closePrice, highPrice, lowPrice, volume, amount float64
		if err := rows.Scan(&symbol, &timestamp, &openPrice, &closePrice, &highPrice, &lowPrice, &volume, &amount); err != nil {
			continue
		}
		if symbol == "" || timestamp == "" || closePrice <= 0 {
			continue
		}
		result[symbol] = append(result[symbol], map[string]any{
			"timestamp": timestamp,
			"open":      openPrice,
			"close":     closePrice,
			"high":      highPrice,
			"low":       lowPrice,
			"volume":    volume,
			"amount":    amount,
			"source":    "mysql_minute_bar_snapshot",
		})
	}
	for symbol, bars := range result {
		sort.SliceStable(bars, func(i, j int) bool {
			return stringField(bars[i], "timestamp") < stringField(bars[j], "timestamp")
		})
		result[symbol] = tailMinuteBars(bars, limit)
	}
	return result, rows.Err()
}

func mysqlDSN(rawURL string) string {
	value := strings.TrimSpace(rawURL)
	if value == "" {
		return ""
	}
	if strings.Contains(value, "@tcp(") {
		return value
	}
	parsed, err := url.Parse(value)
	if err != nil || !strings.HasPrefix(parsed.Scheme, "mysql") || parsed.Host == "" {
		return ""
	}
	user := parsed.User.Username()
	password, _ := parsed.User.Password()
	dbName := strings.Trim(parsed.Path, "/")
	if user == "" || dbName == "" {
		return ""
	}
	return user + ":" + password + "@tcp(" + parsed.Host + ")/" + dbName + "?parseTime=true&charset=utf8mb4"
}

func symbolsFromKeys(keys []string) []string {
	symbols := make([]string, 0, len(keys))
	for _, key := range keys {
		symbol := strings.TrimPrefix(key, quoteCachePrefix)
		if symbol != "" {
			symbols = append(symbols, symbol)
		}
	}
	return dedupeSymbols(symbols)
}

func latestDailyQuoteQuery(symbols []string) (string, []any) {
	placeholders := make([]string, 0, len(symbols))
	args := make([]any, 0, len(symbols))
	for _, symbol := range symbols {
		placeholders = append(placeholders, "?")
		args = append(args, symbol)
	}
	query := `
SELECT d.symbol, COALESCE(i.name, d.symbol), COALESCE(i.market, d.market), COALESCE(i.instrument_type, d.instrument_type),
       d.close_price, d.pct_chg, d.open_price, d.high_price, d.low_price, d.pre_close, d.volume, d.amount, d.trade_date
FROM daily_bar_snapshots d
LEFT JOIN instruments i ON i.symbol = d.symbol
WHERE d.symbol IN (` + strings.Join(placeholders, ",") + `)
  AND d.trade_date = (SELECT MAX(trade_date) FROM daily_bar_snapshots)
`
	return query, args
}

func latestMinuteBarsQuery(symbols []string, period string, limit int) (string, []any) {
	placeholders := make([]string, 0, len(symbols))
	args := make([]any, 0, len(symbols)+2)
	for _, symbol := range symbols {
		placeholders = append(placeholders, "?")
		args = append(args, symbol)
	}
	args = append(args, period, limit)
	query := `
SELECT symbol, bar_timestamp, open_price, close_price, high_price, low_price, volume, amount
FROM (
  SELECT symbol, bar_timestamp, open_price, close_price, high_price, low_price, volume, amount,
         ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bar_timestamp DESC) AS rn
  FROM minute_bar_snapshots
  WHERE symbol IN (` + strings.Join(placeholders, ",") + `)
    AND bar_period = ?
) ranked
WHERE rn <= ?
ORDER BY symbol, bar_timestamp ASC
`
	return query, args
}

func scanDailyQuotePayload(rows *sql.Rows) (map[string]any, error) {
	var symbol, name, market, instrumentType, tradeDate string
	var closePrice, pctChg, openPrice, highPrice, lowPrice, preClose, volume, amount float64
	if err := rows.Scan(&symbol, &name, &market, &instrumentType, &closePrice, &pctChg, &openPrice, &highPrice, &lowPrice, &preClose, &volume, &amount, &tradeDate); err != nil {
		return nil, err
	}
	if symbol == "" || closePrice <= 0 {
		return nil, errors.New("invalid daily quote row")
	}
	changeAmount := closePrice - preClose
	return map[string]any{
		"cached_at": float64(time.Now().Unix()),
		"payload": map[string]any{
			"symbol":               symbol,
			"name":                 name,
			"market":               market,
			"instrument_type":      instrumentType,
			"last_price":           closePrice,
			"change_pct":           pctChg,
			"change_amount":        changeAmount,
			"open_price":           openPrice,
			"high_price":           highPrice,
			"low_price":            lowPrice,
			"prev_close":           preClose,
			"volume":               volume,
			"amount":               amount,
			"timestamp":            tradeDate,
			"data_source":          "mysql_daily_bar_snapshot",
			"source_quality":       "stale",
			"data_quality":         "stale",
			"data_quality_message": "Redis 实时行情未命中，Go 读服务回退到 MySQL 最新日线快照。",
			"is_stale":             true,
		},
	}, nil
}
