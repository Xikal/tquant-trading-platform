package main

import "context"

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
	if batch, ok := cache.secondary.(quoteMultiCache); ok {
		if values, err := batch.MGet(ctx, remaining); err == nil {
			for key, value := range values {
				if len(value) > 0 {
					result[key] = value
				}
			}
		}
	}
	return result, nil
}
