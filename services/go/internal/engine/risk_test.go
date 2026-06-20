package engine

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestStopLossTrigger(t *testing.T) {
	r := NewRiskManager(RiskConfig{StopLossPercent: 5.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 9.0})
	assert.Equal(t, 1, len(orders))
	assert.Equal(t, Sell, orders[0].Side)
}

func TestStopLossNotTriggered(t *testing.T) {
	r := NewRiskManager(RiskConfig{StopLossPercent: 5.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 9.8})
	assert.Equal(t, 0, len(orders))
}

func TestTakeProfitTrigger(t *testing.T) {
	r := NewRiskManager(RiskConfig{TakeProfitPercent: 10.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 12.0})
	assert.Equal(t, 1, len(orders))
	assert.Equal(t, Sell, orders[0].Side)
}

func TestTrailingStopTrigger(t *testing.T) {
	r := NewRiskManager(RiskConfig{TrailingStopPercent: 5.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 11.0})
	assert.Equal(t, 0, len(orders), "price up, trailing not triggered")

	orders = r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 10.2})
	assert.Equal(t, 1, len(orders), "price dropped more than 5% from high of 11")
}

func TestTrailingStopNotTriggeredOnSmallDrop(t *testing.T) {
	r := NewRiskManager(RiskConfig{TrailingStopPercent: 5.0})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 11.0})
	assert.Equal(t, 0, len(orders))

	orders = r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 10.6})
	assert.Equal(t, 0, len(orders), "only 3.6% drop, below 5% trailing threshold")
}

func TestNoRiskConfig(t *testing.T) {
	r := NewRiskManager(RiskConfig{})
	portfolio := &Portfolio{Positions: map[string]*Position{
		"000001": {Symbol: "000001", Size: 100, EntryPrice: 10.0},
	}}
	orders := r.CheckExits(portfolio, &Bar{Symbol: "000001", Close: 5.0})
	assert.Equal(t, 0, len(orders), "no risk config means no exits")
}
