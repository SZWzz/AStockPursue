package market

import (
	"fmt"
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/stretchr/testify/assert"
)

func TestMemoryCacheSetGet(t *testing.T) {
	mc := NewMemoryCache(100*time.Second, 10000)
	bars := []*commonv1.Bar{
		{Symbol: "000001", Open: 10, Close: 11, Timestamp: time.Now().UnixMilli(), Frequency: "1d"},
	}
	key := "000001:1d:20260101:20261231"
	mc.SetBars(key, bars)

	got, ok := mc.GetBars(key)
	assert.True(t, ok)
	assert.Equal(t, len(bars), len(got))
	assert.Equal(t, "000001", got[0].Symbol)
}

func TestMemoryCacheExpiry(t *testing.T) {
	mc := NewMemoryCache(-1*time.Second, 10000) // force expired
	bars := []*commonv1.Bar{{Symbol: "000001"}}
	key := "test:expired"
	mc.SetBars(key, bars)

	_, ok := mc.GetBars(key)
	assert.False(t, ok)
}

func TestMemoryCacheMiss(t *testing.T) {
	mc := NewMemoryCache(100*time.Second, 10000)
	_, ok := mc.GetBars("nonexistent")
	assert.False(t, ok)
}

func TestMemoryCacheEviction(t *testing.T) {
	mc := NewMemoryCache(100*time.Second, 5)
	for i := 0; i < 10; i++ {
		key := fmt.Sprintf("key:%d", i)
		mc.SetBars(key, []*commonv1.Bar{{Symbol: "000001"}})
	}
	// After 10 inserts with maxEntries=5, oldest 20% (1 entry) evicted 5 times = 5 oldest gone
	// Most recent 5 should remain
	for i := 0; i < 5; i++ {
		_, ok := mc.GetBars(fmt.Sprintf("key:%d", i))
		assert.False(t, ok, "key %d should have been evicted", i)
	}
	for i := 5; i < 10; i++ {
		_, ok := mc.GetBars(fmt.Sprintf("key:%d", i))
		assert.True(t, ok, "key %d should still be in cache", i)
	}
}

func TestMemoryCacheDeepCopy(t *testing.T) {
	mc := NewMemoryCache(100*time.Second, 10000)
	bar := &commonv1.Bar{Symbol: "000001", Open: 10, Close: 11, Timestamp: time.Now().UnixMilli(), Frequency: "1d"}
	bars := []*commonv1.Bar{bar}
	key := "test:deepcopy"
	mc.SetBars(key, bars)

	got, ok := mc.GetBars(key)
	assert.True(t, ok)

	// Mutate the returned copy
	got[0].Open = 999

	// Original cache entry should be unchanged
	got2, ok2 := mc.GetBars(key)
	assert.True(t, ok2)
	assert.Equal(t, float64(10), got2[0].Open)
}
