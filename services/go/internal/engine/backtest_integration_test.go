package engine_test

import (
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/engine"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/stretchr/testify/assert"
)

// TestBacktestEndToEnd runs a full backtest with pre-populated local data.
// Exercises: DataStore → BacktestRunner → Engine → Pipeline → Risk → Metrics.
func TestBacktestEndToEnd(t *testing.T) {
	// 1. Populate LocalStore with test bars (unified symbol format)
	dir := t.TempDir()
	localStore := market.NewLocalStore(dir)

	bars := generateTestBars("000001.SZ", 20, 10.0, 0.05)
	err := localStore.SaveBars("000001.SZ", "1d", bars)
	assert.NoError(t, err)

	// 2. Build DataStore with local store + cache
	cache := market.NewMemoryCache(time.Hour, 100)
	ds := market.NewDataStore(nil, cache).WithLocalStore(localStore)

	// 3. Create pipeline with ChinaA engine
	factory := engine.NewEngineFactory()
	p := &engine.Pipeline{
		Engine:    factory.ForSymbol("000001"),
		Portfolio: &engine.Portfolio{
			Cash:      100000,
			Equity:    100000,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   engine.NewNoopSignalAdapter(),
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]*engine.Bar),
	}

	// 4. Run backtest with bare symbol — engine normalizes to "000001.SZ"
	runner := engine.NewBacktestRunner(p, ds)
	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2026, 1, 20, 0, 0, 0, 0, time.UTC)
	result, err := runner.Run([]string{"000001"}, start, end, "1d")

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, 100000.0, result.InitialCash)
	assert.GreaterOrEqual(t, len(result.EquityCurve), 1)
	assert.Equal(t, 0, result.TotalTrades, "noop signal generates no trades")
}

// TestBacktestEndToEndWithSignal tests pipeline with full-allocation signal.
func TestBacktestEndToEndWithSignal(t *testing.T) {
	dir := t.TempDir()
	localStore := market.NewLocalStore(dir)

	bars := generateTestBars("000001.SZ", 20, 10.0, 0.02)
	err := localStore.SaveBars("000001.SZ", "1d", bars)
	assert.NoError(t, err)

	cache := market.NewMemoryCache(time.Hour, 100)
	ds := market.NewDataStore(nil, cache).WithLocalStore(localStore)

	factory := engine.NewEngineFactory()
	p := &engine.Pipeline{
		Engine:    factory.ForSymbol("000001"),
		Portfolio: &engine.Portfolio{
			Cash:      100000,
			Equity:    100000,
			Positions: make(map[string]*engine.Position),
		},
		Signal:   &fullAllocSignal{},
		Risk:     engine.NewRiskManager(engine.RiskConfig{}),
		LastBars: make(map[string]*engine.Bar),
	}

	runner := engine.NewBacktestRunner(p, ds)
	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	end := time.Date(2026, 1, 20, 0, 0, 0, 0, time.UTC)
	result, err := runner.Run([]string{"000001"}, start, end, "1d")

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Greater(t, result.TotalTrades, 0, "should have trades with active signal")
	assert.Greater(t, len(result.Trades), 0)
}

// fullAllocSignal generates 100% allocation to the first available symbol.
type fullAllocSignal struct{}

func (f *fullAllocSignal) Generate(bars map[string]*engine.Bar, ts time.Time) (map[string]float64, error) {
	for sym, bar := range bars {
		if sym != "" {
			return map[string]float64{sym: 1.0}, nil
		}
		_ = bar
	}
	return nil, nil
}

// generateTestBars creates a sequence of bars with a pseudo-random walk.
func generateTestBars(symbol string, count int, basePrice float64, volatility float64) []*commonv1.Bar {
	bars := make([]*commonv1.Bar, 0, count)
	price := basePrice
	start := time.Date(2026, 1, 2, 0, 0, 0, 0, time.UTC)

	rng := uint32(42)
	for i := 0; i < count; i++ {
		rng = rng*1103515245 + 12345
		change := (float64(rng%2000)/1000.0 - 1.0) * volatility * price
		price += change
		if price < 1.0 {
			price = 1.0
		}
		ts := start.Add(time.Duration(i*24) * time.Hour)
		bars = append(bars, &commonv1.Bar{
			Symbol:    symbol,
			Open:      price * 0.99,
			High:      price * 1.02,
			Low:       price * 0.98,
			Close:     price,
			Volume:    1000000,
			Timestamp: ts.UnixMilli(),
			Frequency: "1d",
		})
	}
	return bars
}
