package main

import (
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"sync"
	"time"
)

type workspaceCache struct {
	mu       sync.Mutex
	items    map[string]cachedWorkspaceResponse
	ttl      time.Duration
	staleTTL time.Duration
}

type cachedWorkspaceResponse struct {
	status      int
	body        []byte
	contentType string
	expiresAt   time.Time
	staleUntil  time.Time
}

func newWorkspaceCache(ttl time.Duration) *workspaceCache {
	return newWorkspaceCacheWithStale(ttl, 0)
}

func newWorkspaceCacheWithStale(ttl time.Duration, staleTTL time.Duration) *workspaceCache {
	if ttl <= 0 {
		ttl = 5 * time.Second
	}
	if staleTTL < 0 {
		staleTTL = 0
	}
	return &workspaceCache{
		items:    make(map[string]cachedWorkspaceResponse),
		ttl:      ttl,
		staleTTL: staleTTL,
	}
}

func (cache *workspaceCache) get(key string) (cachedWorkspaceResponse, bool) {
	if cache == nil {
		return cachedWorkspaceResponse{}, false
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	item, ok := cache.items[key]
	now := time.Now()
	if !ok {
		return cachedWorkspaceResponse{}, false
	}
	if now.After(item.expiresAt) {
		if !item.staleUntil.After(now) {
			delete(cache.items, key)
		}
		return cachedWorkspaceResponse{}, false
	}
	return item, true
}

func (cache *workspaceCache) getStale(key string) (cachedWorkspaceResponse, bool) {
	if cache == nil || cache.staleTTL <= 0 {
		return cachedWorkspaceResponse{}, false
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	item, ok := cache.items[key]
	now := time.Now()
	if !ok {
		return cachedWorkspaceResponse{}, false
	}
	if !now.After(item.expiresAt) {
		return cachedWorkspaceResponse{}, false
	}
	if !item.staleUntil.After(now) {
		delete(cache.items, key)
		return cachedWorkspaceResponse{}, false
	}
	return item, true
}

func (cache *workspaceCache) staleEnabled() bool {
	return cache != nil && cache.staleTTL > 0
}

func (cache *workspaceCache) size() int {
	if cache == nil {
		return 0
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	now := time.Now()
	for key, item := range cache.items {
		expiry := item.expiresAt
		if item.staleUntil.After(expiry) {
			expiry = item.staleUntil
		}
		if now.After(expiry) {
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

func (cache *workspaceCache) staleTTLSeconds() float64 {
	if cache == nil {
		return 0
	}
	return cache.staleTTL.Seconds()
}

func (cache *workspaceCache) set(key string, status int, body []byte, contentType string) {
	if cache == nil || status < http.StatusOK || status >= http.StatusMultipleChoices {
		return
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	expiresAt := time.Now().Add(cache.ttl)
	staleUntil := expiresAt
	if cache.staleTTL > 0 {
		staleUntil = expiresAt.Add(cache.staleTTL)
	}
	cache.items[key] = cachedWorkspaceResponse{
		status:      status,
		body:        append([]byte(nil), body...),
		contentType: contentType,
		expiresAt:   expiresAt,
		staleUntil:  staleUntil,
	}
}

func workspaceCacheKey(r *http.Request) string {
	sum := sha256.Sum256([]byte(
		r.Method + "|" + r.URL.Path + "|" + r.URL.RawQuery + "|" +
			r.Header.Get("Authorization") + "|" + r.Header.Get("X-Admin-Token"),
	))
	return hex.EncodeToString(sum[:])
}
