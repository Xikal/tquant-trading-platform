package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type redisQuoteCache struct {
	address  string
	password string
	db       int
	timeout  time.Duration
}

func (cache redisQuoteCache) MinuteBars(ctx context.Context, symbols []string, period string, limit int) (map[string][]map[string]any, error) {
	keys := make([]string, 0, len(symbols))
	keyToSymbol := make(map[string]string, len(symbols))
	for _, symbol := range dedupeSymbols(symbols) {
		key := minuteCachePrefix + period + ":" + symbol
		keys = append(keys, key)
		keyToSymbol[key] = symbol
	}
	if len(keys) == 0 {
		return map[string][]map[string]any{}, nil
	}
	rawValues, err := cache.MGet(ctx, keys)
	if err != nil {
		return nil, err
	}
	result := make(map[string][]map[string]any, len(rawValues))
	for key, raw := range rawValues {
		symbol := keyToSymbol[key]
		bars := parseMinuteBarPayload(raw, limit)
		if symbol != "" && len(bars) > 0 {
			result[symbol] = bars
		}
	}
	return result, nil
}

func newRedisQuoteCache(rawURL string) quoteCache {
	parsed, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil || parsed.Scheme != "redis" || parsed.Host == "" {
		return unavailableCache{}
	}
	password, _ := parsed.User.Password()
	db := 0
	if path := strings.Trim(parsed.Path, "/"); path != "" {
		if parsedDB, err := strconv.Atoi(path); err == nil {
			db = parsedDB
		}
	}
	return redisQuoteCache{
		address:  parsed.Host,
		password: password,
		db:       db,
		timeout:  800 * time.Millisecond,
	}
}

func (cache redisQuoteCache) Get(ctx context.Context, key string) ([]byte, error) {
	values, err := cache.MGet(ctx, []string{key})
	if err != nil {
		return nil, err
	}
	return values[key], nil
}

func (cache redisQuoteCache) MGet(ctx context.Context, keys []string) (map[string][]byte, error) {
	conn, err := (&net.Dialer{Timeout: cache.timeout}).DialContext(ctx, "tcp", cache.address)
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(cache.timeout))
	reader := bufio.NewReader(conn)
	if cache.password != "" {
		if _, err := cache.command(reader, conn, "AUTH", cache.password); err != nil {
			return nil, err
		}
	}
	if cache.db > 0 {
		if _, err := cache.command(reader, conn, "SELECT", strconv.Itoa(cache.db)); err != nil {
			return nil, err
		}
	}
	args := append([]string{"MGET"}, keys...)
	return cache.mgetCommand(reader, conn, args...)
}

func (cache redisQuoteCache) command(reader *bufio.Reader, conn net.Conn, args ...string) ([]byte, error) {
	if _, err := fmt.Fprintf(conn, "*%d\r\n", len(args)); err != nil {
		return nil, err
	}
	for _, arg := range args {
		if _, err := fmt.Fprintf(conn, "$%d\r\n%s\r\n", len(arg), arg); err != nil {
			return nil, err
		}
	}
	return readRESP(reader)
}

func (cache redisQuoteCache) mgetCommand(reader *bufio.Reader, conn net.Conn, args ...string) (map[string][]byte, error) {
	if _, err := fmt.Fprintf(conn, "*%d\r\n", len(args)); err != nil {
		return nil, err
	}
	for _, arg := range args {
		if _, err := fmt.Fprintf(conn, "$%d\r\n%s\r\n", len(arg), arg); err != nil {
			return nil, err
		}
	}
	values, err := readRESPArray(reader)
	if err != nil {
		return nil, err
	}
	result := make(map[string][]byte, len(values))
	for index, value := range values {
		if value == nil {
			continue
		}
		key := args[index+1]
		result[key] = value
	}
	return result, nil
}

type unavailableCache struct{}

func (unavailableCache) Get(context.Context, string) ([]byte, error) {
	return nil, errors.New("redis cache unavailable")
}

func (unavailableCache) MGet(context.Context, []string) (map[string][]byte, error) {
	return nil, errors.New("redis cache unavailable")
}

func (unavailableCache) MinuteBars(context.Context, []string, string, int) (map[string][]map[string]any, error) {
	return nil, errors.New("minute bar cache unavailable")
}

func parseMinuteBarPayload(raw []byte, limit int) []map[string]any {
	if len(raw) == 0 {
		return nil
	}
	var arrayPayload []map[string]any
	if err := json.Unmarshal(raw, &arrayPayload); err == nil {
		return tailMinuteBars(arrayPayload, limit)
	}
	var wrapper map[string]any
	if err := json.Unmarshal(raw, &wrapper); err != nil {
		return nil
	}
	if rawBars, ok := wrapper["bars"].([]any); ok {
		bars := make([]map[string]any, 0, len(rawBars))
		for _, item := range rawBars {
			if row, ok := item.(map[string]any); ok {
				bars = append(bars, normalizeMinuteBar(row))
			}
		}
		return tailMinuteBars(bars, limit)
	}
	if rawPayload, ok := wrapper["payload"].([]any); ok {
		bars := make([]map[string]any, 0, len(rawPayload))
		for _, item := range rawPayload {
			if row, ok := item.(map[string]any); ok {
				bars = append(bars, normalizeMinuteBar(row))
			}
		}
		return tailMinuteBars(bars, limit)
	}
	return nil
}

func normalizeMinuteBar(row map[string]any) map[string]any {
	if row["timestamp"] == nil {
		for _, key := range []string{"bar_timestamp", "time", "datetime"} {
			if value := stringField(row, key); value != "" {
				row["timestamp"] = value
				break
			}
		}
	}
	aliases := map[string][]string{
		"open":   {"open_price"},
		"close":  {"close_price"},
		"high":   {"high_price"},
		"low":    {"low_price"},
		"volume": {"vol"},
		"amount": {"turnover"},
	}
	for target, keys := range aliases {
		if floatField(row, target) != 0 {
			continue
		}
		for _, key := range keys {
			if value := floatField(row, key); value != 0 {
				row[target] = value
				break
			}
		}
	}
	return row
}

func tailMinuteBars(bars []map[string]any, limit int) []map[string]any {
	if limit <= 0 || len(bars) <= limit {
		return bars
	}
	return bars[len(bars)-limit:]
}

func readRESP(reader *bufio.Reader) ([]byte, error) {
	prefix, err := reader.ReadByte()
	if err != nil {
		return nil, err
	}
	switch prefix {
	case '+':
		line, err := reader.ReadString('\n')
		return []byte(strings.TrimSpace(line)), err
	case '-':
		line, _ := reader.ReadString('\n')
		return nil, errors.New(strings.TrimSpace(line))
	case ':':
		line, err := reader.ReadString('\n')
		return []byte(strings.TrimSpace(line)), err
	case '$':
		line, err := reader.ReadString('\n')
		if err != nil {
			return nil, err
		}
		size, err := strconv.Atoi(strings.TrimSpace(line))
		if err != nil {
			return nil, err
		}
		if size < 0 {
			return nil, nil
		}
		payload := make([]byte, size+2)
		if _, err := io.ReadFull(reader, payload); err != nil {
			return nil, err
		}
		return payload[:size], nil
	default:
		return nil, fmt.Errorf("unsupported redis response prefix %q", prefix)
	}
}

func readRESPArray(reader *bufio.Reader) ([][]byte, error) {
	prefix, err := reader.ReadByte()
	if err != nil {
		return nil, err
	}
	if prefix != '*' {
		return nil, fmt.Errorf("expected redis array prefix got %q", prefix)
	}
	line, err := reader.ReadString('\n')
	if err != nil {
		return nil, err
	}
	size, err := strconv.Atoi(strings.TrimSpace(line))
	if err != nil {
		return nil, err
	}
	values := make([][]byte, 0, size)
	for i := 0; i < size; i++ {
		value, err := readRESP(reader)
		if err != nil {
			return nil, err
		}
		values = append(values, value)
	}
	return values, nil
}
