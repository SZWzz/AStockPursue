package engine

import (
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/stretchr/testify/assert"
)

type mockBarLoader struct {
	bars map[string][]*commonv1.Bar
}

func (m *mockBarLoader) GetBars(symbol string, start, end time.Time, freq string) ([]*commonv1.Bar, error) {
	return m.bars[symbol], nil
}

func TestBacktestRunnerSingleSymbol(t *testing.T) {
	loader := &mockBarLoader{
		bars: map[string][]*commonv1.Bar{
			"000001.SZ": {
				{Symbol: "000001.SZ", Open: 10, Close: 10, Volume: 1000, Timestamp: day(1)},
				{Symbol: "000001.SZ", Open: 10, Close: 11, Volume: 1000, Timestamp: day(2)},
				{Symbol: "000001.SZ", Open: 11, Close: 12, Volume: 1000, Timestamp: day(3)},
			},
		},
	}

	signal := &mockSignalAdapter{weight: map[string]float64{"000001.SZ": 0.5}}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]*Bar),
	}

	br := NewBacktestRunner(p, loader)
	result, err := br.Run([]string{"000001"}, time.Now().Add(-10*24*time.Hour), time.Now(), "1d")
	assert.NoError(t, err)
	assert.Equal(t, 100000.0, result.InitialCash)
	assert.Greater(t, result.FinalEquity, 0.0)
	assert.GreaterOrEqual(t, len(result.EquityCurve), 3)
}

func TestBacktestRunnerMetrics(t *testing.T) {
	loader := &mockBarLoader{
		bars: map[string][]*commonv1.Bar{
			"000001.SZ": {
				{Symbol: "000001.SZ", Open: 10, Close: 10, Volume: 1000, Timestamp: day(1)},
				{Symbol: "000001.SZ", Open: 10, Close: 11, Volume: 1000, Timestamp: day(2)},
				{Symbol: "000001.SZ", Open: 11, Close: 12, Volume: 1000, Timestamp: day(3)},
			},
		},
	}

	signal := &mockSignalAdapter{weight: map[string]float64{"000001.SZ": 0.5}}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]*Bar),
	}

	br := NewBacktestRunner(p, loader)
	result, err := br.Run([]string{"000001"}, time.Now().Add(-10*24*time.Hour), time.Now(), "1d")
	assert.NoError(t, err)
	assert.Greater(t, result.TotalReturn, 0.0)
	assert.GreaterOrEqual(t, result.SharpeRatio, 0.0)
	assert.GreaterOrEqual(t, result.MaxDrawdownPct, 0.0)
	assert.LessOrEqual(t, result.MaxDrawdownPct, 1.0)
}

func TestBacktestRunnerNoSignal(t *testing.T) {
	loader := &mockBarLoader{
		bars: map[string][]*commonv1.Bar{
			"000001.SZ": {
				{Symbol: "000001.SZ", Open: 10, Close: 10, Volume: 1000, Timestamp: day(1)},
				{Symbol: "000001.SZ", Open: 10, Close: 10.5, Volume: 1000, Timestamp: day(2)},
			},
		},
	}

	signal := &mockSignalAdapter{weight: map[string]float64{}}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]*Bar),
	}

	br := NewBacktestRunner(p, loader)
	result, err := br.Run([]string{"000001"}, time.Now().Add(-10*24*time.Hour), time.Now(), "1d")
	assert.NoError(t, err)
	assert.Equal(t, 100000.0, result.FinalEquity)
	assert.Equal(t, 0.0, result.TotalReturn)
}

func TestBacktestRunnerMultipleSymbols(t *testing.T) {
	loader := &mockBarLoader{
		bars: map[string][]*commonv1.Bar{
			"000001.SZ": {
				{Symbol: "000001.SZ", Open: 10, Close: 10, Volume: 1000, Timestamp: day(1)},
				{Symbol: "000001.SZ", Open: 10, Close: 11, Volume: 1000, Timestamp: day(2)},
			},
			"600001.SH": {
				{Symbol: "600001.SH", Open: 20, Close: 20, Volume: 1000, Timestamp: day(1)},
				{Symbol: "600001.SH", Open: 20, Close: 22, Volume: 1000, Timestamp: day(2)},
			},
		},
	}

	signal := &mockSignalAdapter{weight: map[string]float64{"000001.SZ": 0.3, "600001.SH": 0.3}}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]*Bar),
	}

	br := NewBacktestRunner(p, loader)
	result, err := br.Run([]string{"000001", "600001"}, time.Now().Add(-10*24*time.Hour), time.Now(), "1d")
	assert.NoError(t, err)
	assert.Equal(t, 2, len(result.EquityCurve))
}

func TestBacktestRunnerEmptyBars(t *testing.T) {
	loader := &mockBarLoader{bars: make(map[string][]*commonv1.Bar)}
	signal := &mockSignalAdapter{}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]*Bar),
	}
	br := NewBacktestRunner(p, loader)
	_, err := br.Run([]string{"000001"}, time.Now(), time.Now(), "1d")
	assert.Error(t, err)
}

func TestNormalizeAStock(t *testing.T) {
	assert.Equal(t, "000001.SZ", normalizeAStock("000001"))
	assert.Equal(t, "600519.SH", normalizeAStock("600519"))
	assert.Equal(t, "002415.SZ", normalizeAStock("002415"))
	assert.Equal(t, "AAPL", normalizeAStock("AAPL"))
	assert.Equal(t, "000001.SZ", normalizeAStock("000001.SZ"))
	assert.Equal(t, "", normalizeAStock(""))
}

func day(d int) int64 {
	return time.Date(2026, 6, d, 9, 30, 0, 0, time.UTC).UnixMilli()
}
