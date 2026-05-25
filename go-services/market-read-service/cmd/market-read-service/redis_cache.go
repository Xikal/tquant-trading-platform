package main

import (
	"bufio"
	"context"
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
