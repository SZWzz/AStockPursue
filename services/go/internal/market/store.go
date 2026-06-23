package market

import (
	"context"
	"fmt"
	slog "github.com/astockpursue/go-core/internal/log"
	"strings"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/db"
	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market/loader"
	"golang.org/x/sync/singleflight"
)

type DataStore struct {
	timescale  *db.TimescaleDB
	localStore *LocalStore
	cache      Cache
	sfGroup    singleflight.Group
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

	v, err, _ := ds.sfGroup.Do(cacheKey, func() (interface{}, error) {
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
							slog.Errorf("[market/store] save bars error: %v", err)
					}
				}
				return bars, nil
			}
		}

		return nil, fmt.Errorf("all data tiers exhausted for %s", symbol)
	})
	if err != nil {
		return nil, err
	}
	return v.([]*commonv1.Bar), nil
}

// GetLatestBars loads the most recent bar for each symbol in the period.
// Satisfies the engine.BarStore interface for signal generation.
func (ds *DataStore) GetLatestBars(symbols []string, start, end time.Time, freq string) (map[string]*engine.Bar, error) {
	key := fmt.Sprintf("bars:%s:%s:%s", strings.Join(symbols, ","), start, end)
	v, err, _ := ds.sfGroup.Do(key, func() (interface{}, error) {
		result := make(map[string]*engine.Bar)
		for _, sym := range symbols {
			bars, err := ds.GetBars(sym, start, end, freq)
			if err != nil || len(bars) == 0 {
				continue
			}
			last := bars[len(bars)-1]
			result[sym] = &engine.Bar{
				Symbol: sym,
				Open:   last.Open,
				High:   last.High,
				Low:    last.Low,
				Close:  last.Close,
				Volume: last.Volume,
			}
		}
		return result, nil
	})
	if err != nil {
		return nil, err
	}
	return v.(map[string]*engine.Bar), nil
}
