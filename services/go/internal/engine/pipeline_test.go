package engine

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

type mockSignalAdapter struct {
	called bool
	weight map[string]float64
	err    error
}

func (m *mockSignalAdapter) Generate(bars []interface{}, ts time.Time) (map[string]float64, error) {
	m.called = true
	return m.weight, m.err
}

type mockRiskPipeline struct {
	called bool
	orders []*Order
}

func (m *mockRiskPipeline) CheckExits(portfolio *Portfolio, bar interface{}) []*Order {
	m.called = true
	return m.orders
}

type mockEngine struct {
	canExec     bool
	roundSizeFn func(float64) float64
	commFn      func(*Order) float64
}

func (m *mockEngine) Name() string                                    { return "mock" }
func (m *mockEngine) CanExecute(order *Order) bool                    { return m.canExec }
func (m *mockEngine) RoundSize(size float64) float64                  { return m.roundSizeFn(size) }
func (m *mockEngine) CalcCommission(order *Order) float64             { return m.commFn(order) }
func (m *mockEngine) ApplySlippage(order *Order, bar interface{}) float64 {
	b := bar.(*Bar)
	return b.Close
}
func (m *mockEngine) CalcMargin(position *Position) float64           { return 0 }
func (m *mockEngine) CalcPnL(position *Position) float64              { return 0 }

func defaultMockEngine() *mockEngine {
	return &mockEngine{
		canExec:     true,
		roundSizeFn: func(f float64) float64 { return f },
		commFn:      func(o *Order) float64 { return 0 },
	}
}

func TestPipelineOnBar(t *testing.T) {
	signal := &mockSignalAdapter{weight: map[string]float64{"000001": 0.5}}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]interface{}),
	}
	p.OnBar(&Bar{Symbol: "000001", Close: 10}, time.Now())
	assert.True(t, signal.called, "signal must be called")
	assert.True(t, risk.called, "risk must be called")
}

func TestPipelineEquityCache(t *testing.T) {
	signal := &mockSignalAdapter{weight: map[string]float64{}}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]interface{}),
	}
	p.OnBar(&Bar{Symbol: "000001", Close: 10}, time.Now())
	assert.Equal(t, 100000.0, p.EquityCache)
}

func TestPipelineGapDetection(t *testing.T) {
	signal := &mockSignalAdapter{weight: map[string]float64{}}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  map[string]interface{}{"000001": &Bar{Symbol: "000001", Close: 10}},
	}
	p.OnBar(&Bar{Symbol: "000001", Open: 11, Close: 10.5}, time.Now())
	assert.True(t, signal.called)
}

func TestPipelineSuspensionDetection(t *testing.T) {
	signal := &mockSignalAdapter{weight: map[string]float64{}}
	risk := &mockRiskPipeline{}
	p := &Pipeline{
		Engine: defaultMockEngine(), Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]interface{}),
	}
	p.OnBar(&Bar{Symbol: "000001", Open: 10, Close: 10, Volume: 0}, time.Now())
	assert.True(t, signal.called)
}

func TestPipelineExecuteBuyOrder(t *testing.T) {
	signal := &mockSignalAdapter{weight: map[string]float64{"000001": 0.5}}
	risk := &mockRiskPipeline{}
	me := &mockEngine{
		canExec:     true,
		roundSizeFn: func(f float64) float64 { return f },
		commFn:      func(o *Order) float64 { return 0 },
	}
	p := &Pipeline{
		Engine: me, Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]interface{}),
	}
	p.OnBar(&Bar{Symbol: "000001", Close: 10}, time.Now())
	assert.Equal(t, float64(5000), p.Portfolio.Positions["000001"].Size)
	assert.InDelta(t, 50000, p.Portfolio.Cash, 0.01)
}

func TestPipelineExecuteSellOrder(t *testing.T) {
	signal := &mockSignalAdapter{weight: map[string]float64{"000001": -0.3}}
	risk := &mockRiskPipeline{}
	me := &mockEngine{
		canExec:     true,
		roundSizeFn: func(f float64) float64 { return f },
		commFn:      func(o *Order) float64 { return 0 },
	}
	p := &Pipeline{
		Engine: me, Signal: signal, Risk: risk,
		Portfolio: &Portfolio{
			Cash: 50000, Equity: 100000,
			Positions: map[string]*Position{
				"000001": {Symbol: "000001", Size: 1000, EntryPrice: 10},
			},
		},
		LastBars: make(map[string]interface{}),
	}
	p.OnBar(&Bar{Symbol: "000001", Close: 10}, time.Now())
	assert.NotContains(t, p.Portfolio.Positions, "000001")
	assert.InDelta(t, 60000, p.Portfolio.Cash, 0.01)
}

func TestPipelineEquityRecording(t *testing.T) {
	signal := &mockSignalAdapter{weight: map[string]float64{"000001": 0.5}}
	risk := &mockRiskPipeline{}
	me := &mockEngine{
		canExec:     true,
		roundSizeFn: func(f float64) float64 { return f },
		commFn:      func(o *Order) float64 { return 0 },
	}
	p := &Pipeline{
		Engine: me, Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 100000, Equity: 100000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]interface{}),
	}
	p.OnBar(&Bar{Symbol: "000001", Close: 10}, time.Now())
	// Buy 5000 shares at 10 -> positions worth 50000 + cash 50000 = 100000
	assert.InDelta(t, 100000, p.Portfolio.Equity, 0.01)
}

func TestPipelineNotEnoughCash(t *testing.T) {
	signal := &mockSignalAdapter{weight: map[string]float64{"000001": 2.0}} // 200% of equity
	risk := &mockRiskPipeline{}
	me := &mockEngine{
		canExec:     true,
		roundSizeFn: func(f float64) float64 { return f },
		commFn:      func(o *Order) float64 { return 0 },
	}
	p := &Pipeline{
		Engine: me, Signal: signal, Risk: risk,
		Portfolio: &Portfolio{Cash: 10000, Equity: 10000, Positions: make(map[string]*Position)},
		LastBars:  make(map[string]interface{}),
	}
	p.OnBar(&Bar{Symbol: "000001", Close: 10}, time.Now())
	// 200% * 10000 / 10 = 2000 shares, but only 10000 cash = 1000 shares max
	assert.Equal(t, float64(1000), p.Portfolio.Positions["000001"].Size)
}
