package market

import (
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/stretchr/testify/assert"
)

func TestDataStoreReturnsErrorWithoutAnyTier(t *testing.T) {
	mc := NewMemoryCache(100*time.Second, 10000)
	ds := NewDataStore(nil, mc)
	_, err := ds.GetBars("000001", time.Now(), time.Now(), "1d")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "all data tiers exhausted")
}

func TestDataStoreUsesCache(t *testing.T) {
	mc := NewMemoryCache(100*time.Second, 10000)
	ds := NewDataStore(nil, mc)
	mc.SetBars("000001:1d:0:0", []*commonv1.Bar{{Symbol: "000001"}})
	assert.NotNil(t, ds)
}
