package market

import (
	"sync"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"google.golang.org/protobuf/proto"
)

type Cache interface {
	GetBars(key string) ([]*commonv1.Bar, bool)
	SetBars(key string, bars []*commonv1.Bar)
}

type MemoryCache struct {
	mu         sync.RWMutex
	data       map[string]cacheEntry
	keys       []string
	ttl        time.Duration
	maxEntries int
}

type cacheEntry struct {
	bars      []*commonv1.Bar
	expiresAt time.Time
}

func NewMemoryCache(ttl time.Duration, maxEntries int) *MemoryCache {
	if maxEntries <= 0 {
		maxEntries = 10000
	}
	return &MemoryCache{
		data:       make(map[string]cacheEntry),
		keys:       make([]string, 0, maxEntries),
		ttl:        ttl,
		maxEntries: maxEntries,
	}
}

func (mc *MemoryCache) GetBars(key string) ([]*commonv1.Bar, bool) {
	mc.mu.RLock()
	defer mc.mu.RUnlock()
	entry, ok := mc.data[key]
	if !ok || time.Now().After(entry.expiresAt) {
		return nil, false
	}
	result := make([]*commonv1.Bar, len(entry.bars))
	for i, bar := range entry.bars {
		result[i] = proto.Clone(bar).(*commonv1.Bar)
	}
	return result, true
}

func (mc *MemoryCache) SetBars(key string, bars []*commonv1.Bar) {
	mc.mu.Lock()
	defer mc.mu.Unlock()

	if _, exists := mc.data[key]; !exists {
		if len(mc.data) >= mc.maxEntries {
			evict := len(mc.data) / 5
			if evict < 1 {
				evict = 1
			}
			for i := 0; i < evict; i++ {
				delete(mc.data, mc.keys[0])
				mc.keys = mc.keys[1:]
			}
		}
		mc.keys = append(mc.keys, key)
	}

	mc.data[key] = cacheEntry{
		bars:      bars,
		expiresAt: time.Now().Add(mc.ttl),
	}
}
