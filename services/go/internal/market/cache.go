package market

import (
	"sync"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
)

type Cache interface {
	GetBars(key string) ([]*commonv1.Bar, bool)
	SetBars(key string, bars []*commonv1.Bar)
}

type MemoryCache struct {
	mu  sync.RWMutex
	data map[string]cacheEntry
	ttl time.Duration
}

type cacheEntry struct {
	bars      []*commonv1.Bar
	expiresAt time.Time
}

func NewMemoryCache(ttl time.Duration) *MemoryCache {
	return &MemoryCache{
		data: make(map[string]cacheEntry),
		ttl:  ttl,
	}
}

func (mc *MemoryCache) GetBars(key string) ([]*commonv1.Bar, bool) {
	mc.mu.RLock()
	defer mc.mu.RUnlock()
	entry, ok := mc.data[key]
	if !ok || time.Now().After(entry.expiresAt) {
		return nil, false
	}
	return entry.bars, true
}

func (mc *MemoryCache) SetBars(key string, bars []*commonv1.Bar) {
	mc.mu.Lock()
	defer mc.mu.Unlock()
	mc.data[key] = cacheEntry{
		bars:      bars,
		expiresAt: time.Now().Add(mc.ttl),
	}
}
