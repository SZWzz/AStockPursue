package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestEngineFactoryForSymbol(t *testing.T) {
	f := NewEngineFactory()

	e1 := f.ForSymbol("000001")
	assert.Equal(t, "china_a", e1.Name())

	e2 := f.ForSymbol("600001")
	assert.Equal(t, "china_a", e2.Name())

	e3 := f.ForSymbol("300001")
	assert.Equal(t, "china_a", e3.Name())
}

func TestEngineFactoryRegister(t *testing.T) {
	f := NewEngineFactory()
	f.Register("custom", &ChinaAEngine{})

	e, ok := f.Get("custom")
	assert.True(t, ok)
	assert.Equal(t, "china_a", e.Name())
}

func TestCompositeEngineDelegation(t *testing.T) {
	f := NewEngineFactory()
	c := NewCompositeEngine(f)

	order := &Order{Symbol: "000001", Quantity: 100, Price: 10.0, Side: Buy}
	comm := c.CalcCommission(order)
	assert.Equal(t, 5.0, comm)

	canExec := c.CanExecute(order)
	assert.True(t, canExec)

	size := c.RoundSize(101)
	assert.Equal(t, 100.0, size)
}

func TestCompositeEngineApplySlippage(t *testing.T) {
	f := NewEngineFactory()
	c := NewCompositeEngine(f)

	price := c.ApplySlippage(&Order{Symbol: "000001", Side: Buy}, &Bar{Symbol: "000001", Close: 10.0})
	assert.InDelta(t, 10.01, price, 0.001)
}

func TestCompositeEngineMarginAndPnL(t *testing.T) {
	f := NewEngineFactory()
	c := NewCompositeEngine(f)

	pos := &Position{Symbol: "000001", Size: 100, EntryPrice: 10.0, CurrentPrice: 11.0}
	assert.Equal(t, 0.0, c.CalcMargin(pos))
	assert.InDelta(t, 100.0, c.CalcPnL(pos), 0.01)
}

func TestEngineFactoryForCrypto(t *testing.T) {
	f := NewEngineFactory()
	e := f.ForSymbol("BTCUSDT")
	assert.Equal(t, "crypto", e.Name())
}

func TestEngineFactoryForForex(t *testing.T) {
	f := NewEngineFactory()
	e := f.ForSymbol("EURUSD")
	assert.Equal(t, "forex", e.Name())
}

func TestEngineFactoryForChinaFutures(t *testing.T) {
	f := NewEngineFactory()
	e := f.ForSymbol("IF")
	assert.Equal(t, "china_futures", e.Name())
}

func TestEngineFactoryForGlobalFutures(t *testing.T) {
	f := NewEngineFactory()
	e := f.ForSymbol("ES")
	assert.Equal(t, "global_futures", e.Name())
}

func TestEngineFactoryForOptions(t *testing.T) {
	f := NewEngineFactory()
	e := f.ForSymbol("AAPL.OPT")
	assert.Equal(t, "options", e.Name())
}

func TestEngineFactoryForGlobalEquity(t *testing.T) {
	f := NewEngineFactory()
	e := f.ForSymbol("AAPL")
	assert.Equal(t, "global_equity", e.Name())
}

func TestEngineFactoryForGlobalEquityHSTech(t *testing.T) {
	f := NewEngineFactory()
	e := f.ForSymbol("0700")
	assert.Equal(t, "china_a", e.Name(), "numeric code should route to china_a")
}

func TestEngineFactoryChinaFuturesExactMatch(t *testing.T) {
	f := NewEngineFactory()
	// "AU" is gold futures, NOT AUD forex
	e := f.ForSymbol("AU")
	assert.Equal(t, "china_futures", e.Name())
}
