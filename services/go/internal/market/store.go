package market

import (
	"context"
	"fmt"
	"log"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/db"
	"github.com/astockpursue/go-core/internal/market/loader"
)

type DataStore struct {
	timescale  *db.TimescaleDB
	localStore *LocalStore
	cache      Cache
}

func NewDataStore(ts *db.TimescaleDB, cache Cache) *DataStore {
	return &DataStore{timescale: ts, cache: cache}
}

// WithLocalStore sets the Tier 2 local file store for persisting bar data to disk.
func (ds *DataStore) WithLocalStore(ls *LocalStore) *DataStore {
	ds.localStore = ls
	return ds
}

func (ds *DataStore) GetBars(symbol string, start, end time.Time, freq string) ([]*commonv1.Bar, error) {
	cacheKey := fmt.Sprintf("%s:%s:%d:%d", symbol, freq, start.Unix(), end.Unix())

	if bars, ok := ds.cache.GetBars(cacheKey); ok {
		return bars, nil
	}

	if ds.timescale != nil {
		bars, err := ds.timescale.QueryBars(context.Background(), db.BarQuery{
			Symbol: symbol, StartTime: start, EndTime: end, Frequency: freq,
		})
		if err == nil && len(bars) > 0 {
			ds.cache.SetBars(cacheKey, bars)
			return bars, nil
		}
	}

	// Tier 2: Local file store (JSONL)
	if ds.localStore != nil {
		bars, err := ds.localStore.LoadBars(symbol, start, end, freq)
		if err == nil && len(bars) > 0 {
			ds.cache.SetBars(cacheKey, bars)
			return bars, nil
		}
	}

	// Tier 3: Loader API (fallback chain)
	available := loader.GetAvailable()
	for _, l := range available {
		bars, err := l.FetchBars(symbol, start, end)
		if err == nil && len(bars) > 0 {
			ds.cache.SetBars(cacheKey, bars)
			// Persist to local store for future use
			if ds.localStore != nil {
				if err := ds.localStore.SaveBars(symbol, freq, bars); err != nil {
					log.Printf("[market/store] save bars error: %v", err)
				}
			}
			return bars, nil
		}
	}

	return nil, fmt.Errorf("all data tiers exhausted for %s", symbol)
}
