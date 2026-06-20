package market

import (
	"fmt"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/db"
	"github.com/astockpursue/go-core/internal/market/loader"
)

type DataStore struct {
	timescale *db.TimescaleDB
	cache     Cache
}

func NewDataStore(ts *db.TimescaleDB, cache Cache) *DataStore {
	return &DataStore{timescale: ts, cache: cache}
}

func (ds *DataStore) GetBars(symbol string, start, end time.Time, freq string) ([]*commonv1.Bar, error) {
	cacheKey := fmt.Sprintf("%s:%s:%d:%d", symbol, freq, start.Unix(), end.Unix())

	if bars, ok := ds.cache.GetBars(cacheKey); ok {
		return bars, nil
	}

	if ds.timescale != nil {
		bars, err := ds.timescale.QueryBars(nil, db.BarQuery{
			Symbol: symbol, StartTime: start, EndTime: end, Frequency: freq,
		})
		if err == nil && len(bars) > 0 {
			ds.cache.SetBars(cacheKey, bars)
			return bars, nil
		}
	}

	available := loader.GetAvailable()
	for _, l := range available {
		bars, err := l.FetchBars(symbol, start, end)
		if err == nil && len(bars) > 0 {
			ds.cache.SetBars(cacheKey, bars)
			return bars, nil
		}
	}

	return nil, fmt.Errorf("all data tiers exhausted for %s", symbol)
}
