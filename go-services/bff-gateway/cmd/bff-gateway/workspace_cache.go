package main

import (
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"sync"
	"time"
)

type workspaceCache struct {
	mu    sync.Mutex
	items map[string]cachedWorkspaceResponse
	ttl   time.Duration
}

type cachedWorkspaceResponse struct {
	status      int
	body        []byte
	contentType string
	expiresAt   time.Time
}

func newWorkspaceCache(ttl time.Duration) *workspaceCache {
	if ttl <= 0 {
		ttl = 5 * time.Second
	}
	return &workspaceCache{
		items: make(map[string]cachedWorkspaceResponse),
		ttl:   ttl,
	}
}

func (cache *workspaceCache) get(key string) (cachedWorkspaceResponse, bool) {
	if cache == nil {
		return cachedWorkspaceResponse{}, false
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	item, ok := cache.items[key]
	if !ok || time.Now().After(item.expiresAt) {
		if ok {
			delete(cache.items, key)
		}
		return cachedWorkspaceResponse{}, false
	}
	return item, true
}

func (cache *workspaceCache) size() int {
	if cache == nil {
		return 0
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	now := time.Now()
	for key, item := range cache.items {
		if now.After(item.expiresAt) {
			delete(cache.items, key)
		}
	}
	return len(cache.items)
}

func (cache *workspaceCache) ttlSeconds() float64 {
	if cache == nil {
		return 0
	}
	return cache.ttl.Seconds()
}

func (cache *workspaceCache) set(key string, status int, body []byte, contentType string) {
	if cache == nil || status < http.StatusOK || status >= http.StatusMultipleChoices {
		return
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	cache.items[key] = cachedWorkspaceResponse{
		status:      status,
		body:        append([]byte(nil), body...),
		contentType: contentType,
		expiresAt:   time.Now().Add(cache.ttl),
	}
}

func workspaceCacheKey(r *http.Request) string {
	sum := sha256.Sum256([]byte(
		r.Method + "|" + r.URL.Path + "|" + r.URL.RawQuery + "|" +
			r.Header.Get("Authorization") + "|" + r.Header.Get("X-Admin-Token"),
	))
	return hex.EncodeToString(sum[:])
}
