package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func newTestCrypto() *CryptoEngine {
	return &CryptoEngine{
		MakerFee:          0.0002,
		TakerFee:          0.0006,
		Slippage:          0.001,
		Leverage:          10,
		MaintenanceMargin: 0.005,
		Precision:         map[string]float64{"BTCUSDT": 0.001, "ETHUSDT": 0.01},
	}
}

func TestCryptoName(t *testing.T) {
	e := newTestCrypto()
	assert.Equal(t, "crypto", e.Name())
}

func TestCryptoRoundSize(t *testing.T) {
	e := newTestCrypto()
	assert.Equal(t, 0.001, e.RoundSize(0.0015))
}

func TestCryptoRoundSizeDefault(t *testing.T) {
	e := newTestCrypto()
	assert.Equal(t, 1.5, e.RoundSize(1.5))
}

func TestCryptoCommissionTaker(t *testing.T) {
	e := newTestCrypto()
	order := &Order{Quantity: 1, Price: 50000, Type: Market}
	assert.InDelta(t, 30.0, e.CalcCommission(order), 0.01)
}

func TestCryptoCommissionMaker(t *testing.T) {
	e := newTestCrypto()
	order := &Order{Quantity: 1, Price: 50000, Type: Limit}
	assert.InDelta(t, 10.0, e.CalcCommission(order), 0.01)
}

func TestCryptoMargin(t *testing.T) {
	e := newTestCrypto()
	pos := &Position{Size: 1, CurrentPrice: 50000}
	assert.InDelta(t, 5000.0, e.CalcMargin(pos), 0.01)
}

func TestCryptoMarginShort(t *testing.T) {
	e := newTestCrypto()
	pos := &Position{Size: -2, CurrentPrice: 50000}
	assert.InDelta(t, 10000.0, e.CalcMargin(pos), 0.01)
}

func TestCryptoPnLLong(t *testing.T) {
	e := newTestCrypto()
	pos := &Position{Size: 1, EntryPrice: 40000, CurrentPrice: 50000}
	assert.InDelta(t, 10000.0, e.CalcPnL(pos), 0.01)
}

func TestCryptoPnLShort(t *testing.T) {
	e := newTestCrypto()
	pos := &Position{Size: -1, EntryPrice: 50000, CurrentPrice: 40000}
	assert.InDelta(t, 10000.0, e.CalcPnL(pos), 0.01)
}

func TestCryptoCanExecuteBothSides(t *testing.T) {
	e := newTestCrypto()
	assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Buy}))
	assert.True(t, e.CanExecute(&Order{Quantity: 1, Side: Sell}))
}

func TestCryptoSlippageBuy(t *testing.T) {
	e := newTestCrypto()
	price := e.ApplySlippage(&Order{Side: Buy}, &Bar{Close: 50000})
	assert.InDelta(t, 50050.0, price, 0.01)
}

func TestCryptoSlippageSell(t *testing.T) {
	e := newTestCrypto()
	price := e.ApplySlippage(&Order{Side: Sell}, &Bar{Close: 50000})
	assert.InDelta(t, 49950.0, price, 0.01)
}

func TestCryptoLiquidationLong(t *testing.T) {
	e := newTestCrypto()
	pos := &Position{Size: 1, EntryPrice: 50000}
	assert.InDelta(t, 45250.0, e.LiquidationPrice(pos), 0.01)
}

func TestCryptoLiquidationShort(t *testing.T) {
	e := newTestCrypto()
	pos := &Position{Size: -1, EntryPrice: 50000}
	assert.InDelta(t, 54750.0, e.LiquidationPrice(pos), 0.01)
}
