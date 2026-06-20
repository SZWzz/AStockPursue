package market

import (
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/stretchr/testify/assert"
)

func TestMemoryCacheSetGet(t *testing.T) {
	mc := NewMemoryCache(100 * time.Second)
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
	mc := NewMemoryCache(-1 * time.Second) // force expired
	bars := []*commonv1.Bar{{Symbol: "000001"}}
	key := "test:expired"
	mc.SetBars(key, bars)

	_, ok := mc.GetBars(key)
	assert.False(t, ok)
}

func TestMemoryCacheMiss(t *testing.T) {
	mc := NewMemoryCache(100 * time.Second)
	_, ok := mc.GetBars("nonexistent")
	assert.False(t, ok)
}
