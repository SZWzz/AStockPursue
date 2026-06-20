package engine

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestPositionCalculations(t *testing.T) {
	pos := &Position{Symbol: "000001", Size: 100, EntryPrice: 10.0}
	pos.CurrentPrice = 11.0
	assert.InDelta(t, 100.0, pos.UnrealizedPnL(), 0.01)
	assert.Equal(t, "long", pos.Side())
}

func TestOrderValidation(t *testing.T) {
	o := &Order{Symbol: "000001", Side: "buy", Type: "market", Quantity: 100}
	assert.NoError(t, o.Validate())
	o.Side = "invalid"
	assert.Error(t, o.Validate())
}

func TestPortfolioInitialization(t *testing.T) {
	p := &Portfolio{Cash: 100000}
	p.Positions = make(map[string]*Position)
	assert.Equal(t, 100000.0, p.Cash)
}

func TestOrderConstants(t *testing.T) {
	assert.Equal(t, OrderSide("buy"), Buy)
	assert.Equal(t, OrderSide("sell"), Sell)
	assert.Equal(t, OrderType("market"), Market)
	assert.Equal(t, OrderType("limit"), Limit)
	assert.Equal(t, OrderStatus("pending"), OrderPending)
	assert.Equal(t, OrderStatus("filled"), OrderFilled)
	assert.Equal(t, OrderStatus("cancelled"), OrderCancelled)
	assert.Equal(t, OrderStatus("rejected"), OrderRejected)
}

func TestOrderValidateInvalidType(t *testing.T) {
	o := &Order{Symbol: "000001", Side: "buy", Type: "invalid", Quantity: 100}
	err := o.Validate()
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid type")
}

func TestOrderValidateZeroQuantity(t *testing.T) {
	o := &Order{Symbol: "000001", Side: "buy", Type: "market", Quantity: 0}
	err := o.Validate()
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "quantity must be positive")
}

func TestPositionSideShort(t *testing.T) {
	pos := &Position{Symbol: "000001", Size: -50, EntryPrice: 10.0}
	assert.Equal(t, "short", pos.Side())
}

func TestPositionSideLong(t *testing.T) {
	pos := &Position{Symbol: "000001", Size: 50, EntryPrice: 10.0}
	assert.Equal(t, "long", pos.Side())
}

func TestPositionZeroSize(t *testing.T) {
	pos := &Position{Symbol: "000001", Size: 0, EntryPrice: 10.0}
	assert.Equal(t, "long", pos.Side())
}

func TestPositionUnrealizedPnLShort(t *testing.T) {
	pos := &Position{Symbol: "000001", Size: -100, EntryPrice: 10.0}
	pos.CurrentPrice = 9.0
	assert.InDelta(t, 100.0, pos.UnrealizedPnL(), 0.01)
}

func TestPositionUnrealizedPnLZeroSize(t *testing.T) {
	pos := &Position{Symbol: "000001", Size: 0, EntryPrice: 10.0}
	pos.CurrentPrice = 11.0
	assert.InDelta(t, 0.0, pos.UnrealizedPnL(), 0.01)
}

func TestOrderCreatedAt(t *testing.T) {
	now := time.Now()
	o := &Order{Symbol: "000001", Side: "buy", Type: "limit", Quantity: 100, Price: 10.5, CreatedAt: now}
	assert.Equal(t, 10.5, o.Price)
	assert.Equal(t, now, o.CreatedAt)
}

func TestEngineInterface(t *testing.T) {
	var e Engine
	assert.Nil(t, e)
}

func TestOrderJSONTags(t *testing.T) {
	o := Order{
		Symbol:   "000001",
		Side:     "buy",
		Type:     "market",
		Quantity: 100,
		Filled:   0,
		Status:   "pending",
	}
	assert.Equal(t, "000001", o.Symbol)
	assert.Equal(t, OrderSide("buy"), o.Side)
}
